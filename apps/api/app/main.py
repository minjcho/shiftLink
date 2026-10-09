from contextlib import asynccontextmanager
import os
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Query, Request as HttpRequest
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import COOKIE_NAME, check_origin, principal_data, principal_from_request, rotate_demo_session
from app.core.config import Settings
from app.core.contracts import IncidentStatus
from app.core.db import create_session_factory
from app.core.errors import DomainError, not_found
from app.core.models import Equipment, Evidence, Incident, Job, Shift
from app.core.ports import production_ports
from app.features.actions.commands import ApprovalCommand, CompletionCommand, StartCommand
from app.features.actions.responses import ApprovalResult, CompletionResult, StartResult, SuccessEnvelope
from app.features.actions import orm as actions
from app.core.transactions import execute_command
from app.features.intake.schemas import DemoSessionBody, MessageBody, ReportBody, RetryBody
from app.features.intake import service
from app.features.resolution import service as resolution
from app.features.resolution.router import register_routes as register_resolution_routes


def with_meta(request, body):
    return {**body, "meta": {"request_id": getattr(request.state, "request_id", str(uuid4())),
        "dataset_id": request.app.state.settings.dataset_id, "demo_mode": request.app.state.settings.app_env != "production"}}


def command(request, body, handler, scope=None, idempotency_key=None):
    check_origin(request)
    principal = principal_from_request(request)
    if scope is not None:
        with request.app.state.session_factory() as tx:
            scope(tx, principal)
    def wrapped(tx):
        status, payload = handler(tx, principal)
        return status, with_meta(request, payload)
    segments = []
    for segment in request.url.path.split("/"):
        try:
            segments.append(str(UUID(segment)))
        except ValueError:
            segments.append(segment)
    normalized_route = "/".join(segments)
    status, result, replayed = execute_command(request.app.state.session_factory, principal,
        idempotency_key if idempotency_key is not None else request.headers.get("idempotency-key"), request.method, normalized_route,
        body.model_dump(mode="json"), wrapped)
    return JSONResponse(result, status_code=status, headers={"Idempotent-Replayed": "true"} if replayed else {})


def create_app(database_url=None, settings=None, ports=None, session_factory=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        settings.validate()
        yield

    app = FastAPI(title="ShiftLink", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory or create_session_factory(database_url or settings.database_url)
    app.state.ports = ports if ports is not None else production_ports()
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=True,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"],
                       expose_headers=["Idempotent-Replayed"])

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        return await call_next(request)

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        return JSONResponse(with_meta(request, error.body()), status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = {"fields": [{"location": list(e["loc"]), "type": e["type"]} for e in error.errors()]}
        return JSONResponse(with_meta(request, DomainError(422, "VALIDATION_ERROR", "입력 형식을 확인해 주세요.", details=details).body()), status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return JSONResponse(with_meta(request, DomainError(503, "SERVICE_UNAVAILABLE", "저장소에 연결할 수 없습니다. 같은 요청으로 다시 시도해 주세요.", retryable=True).body()), status_code=503)

    @app.post("/api/v1/demo/session")
    def demo_session(request: HttpRequest, body: DemoSessionBody):
        raw, data = rotate_demo_session(request, body.account_key)
        response = JSONResponse(with_meta(request, {"data": data}))
        response.set_cookie(COOKIE_NAME, raw, httponly=True, secure=settings.session_cookie_secure,
                            samesite="lax", max_age=43200, path="/")
        return response

    @app.get("/healthz", include_in_schema=False)
    def health():
        with app.state.session_factory() as tx:
            tx.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/api/v1/me")
    def me(request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            result = with_meta(request, {"data": principal_data(tx, principal)})
            result["meta"]["build"] = {"app_commit_sha": os.environ.get("APP_COMMIT_SHA"),
                "working_tree_dirty": None, "agent_mode": settings.agent_mode, "search_mode": "keyword"}
            return result

    @app.get("/api/v1/equipment")
    def equipment(request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            rows = tx.scalars(select(Equipment).where(Equipment.site_id == principal.site_id).order_by(Equipment.code))
            return with_meta(request, {"data": {"items": [{"id": x.id, "code": x.code, "label": x.label, "aliases": x.aliases} for x in rows], "next_cursor": None}})

    @app.get("/api/v1/shifts")
    def shifts(request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            rows = list(tx.scalars(select(Shift).where(Shift.site_id == principal.site_id).order_by(Shift.starts_at)))
            return with_meta(request, {"data": {"items": [service.as_dict(x) for x in rows],
                "allowed_pairs": [{"from_shift_occurrence_id": a.id, "to_shift_occurrence_id": b.id}
                                  for a, b in zip(rows, rows[1:]) if a.ends_at == b.starts_at], "next_cursor": None}})

    @app.post("/api/v1/incidents")
    def report(request: HttpRequest, body: ReportBody):
        return command(request, body, lambda tx, actor: service.create_report(tx, actor, body, app.state.ports))

    @app.post("/api/v1/incidents/{incident_id}/messages")
    def message(incident_id: UUID, request: HttpRequest, body: MessageBody):
        return command(request, body, lambda tx, actor: service.add_message(tx, actor, str(incident_id), body, app.state.ports))

    @app.get("/api/v1/incidents")
    def incidents(request: HttpRequest, status: IncidentStatus | None = None,
                  equipment_id: UUID | None = None, scope: Literal["all", "mine"] = "all",
                  cursor: str | None = Query(default=None, max_length=2048), limit: int = Query(default=20, ge=1, le=100)):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            return with_meta(request, {"data": service.list_incidents(tx, principal, status=status,
                equipment_id=str(equipment_id) if equipment_id else None, scope=scope, cursor=cursor, limit=limit)})

    @app.get("/api/v1/incidents/{incident_id}")
    def incident(incident_id: UUID, request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory.begin() as tx:
            # A coherent displayed version + readiness; all business writers lock Incident first.
            row = tx.scalar(select(Incident).where(Incident.id == str(incident_id),
                Incident.site_id == principal.site_id).with_for_update(read=True))
            if row is None:
                raise not_found()
            data = service.detail(tx, principal, str(incident_id), settings)
            data["resolution"] = resolution.detail(tx, principal, row, app.state.ports)
            return with_meta(request, {"data": data})

    @app.get("/api/v1/jobs/{job_id}")
    def job(job_id: UUID, request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            row = tx.get(Job, str(job_id))
            if row is None:
                raise not_found()
            incident = service.read_incident(tx, principal, row.incident_id)
            return with_meta(request, {"data": service.job_data(tx, principal, row, incident, settings)})

    @app.post("/api/v1/jobs/{job_id}/retry")
    def retry(job_id: UUID, request: HttpRequest, body: RetryBody):
        return command(request, body, lambda tx, actor: service.retry_job(tx, actor, str(job_id), settings))

    @app.get("/api/v1/evidence/{evidence_id}")
    def evidence(evidence_id: UUID, request: HttpRequest):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            row = tx.scalar(select(Evidence).where(Evidence.id == str(evidence_id), Evidence.site_id == principal.site_id))
            if row is None:
                raise not_found()
            service.read_incident(tx, principal, row.incident_id)
            return with_meta(request, {"data": service.as_dict(row)})

    def action_command(action_id, request, body, idempotency_key):
        return command(request, body,
            lambda tx, actor: actions.execute(tx, actor, action_id, body, app.state.ports),
            scope=lambda tx, actor: actions.assert_scope(tx, actor, action_id),
            idempotency_key=idempotency_key)

    @app.post("/api/v1/actions/{action_id}/approval-decisions", response_model=SuccessEnvelope[ApprovalResult])
    def approval(action_id: UUID, request: HttpRequest, body: ApprovalCommand,
                 idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]):
        return action_command(action_id, request, body, idempotency_key)

    @app.post("/api/v1/actions/{action_id}/start", response_model=SuccessEnvelope[StartResult])
    def start_action(action_id: UUID, request: HttpRequest, body: StartCommand,
                 idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]):
        return action_command(action_id, request, body, idempotency_key)

    @app.post("/api/v1/actions/{action_id}/completion", response_model=SuccessEnvelope[CompletionResult])
    def complete_action(action_id: UUID, request: HttpRequest, body: CompletionCommand,
                 idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]):
        return action_command(action_id, request, body, idempotency_key)

    register_resolution_routes(app, command, with_meta)
    return app


app = create_app()
