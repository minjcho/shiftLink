from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text

from .core.config import load_settings
from .core.contracts import SessionView, Envelope
from .core.database import make_engine
from .core.errors import DomainError, error_response, install_error_handlers, request_meta
from .core.sessions import COOKIE_NAME, SESSION_SECONDS, current_session, rotate_session, read_session
from .core.schema import equipment, shifts, shift_pairs


class SessionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_key: Literal["reporter", "maintainer", "outgoing_supervisor", "incoming_supervisor"]


def create_app(settings=None, engine=None):
    settings = settings or load_settings()
    owned_engine = engine is None
    engine = engine if engine is not None else make_engine(settings)

    @asynccontextmanager
    async def lifespan(app):
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text("SELECT version_num FROM alembic_version"))
        yield
        if owned_engine:
            engine.dispose()

    app = FastAPI(title="ShiftLink", version="0.3.0", lifespan=lifespan)
    app.state.settings, app.state.engine = settings, engine
    install_error_handlers(app)
    app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def context_and_origin(request: Request, call_next):
        request.state.request_id = str(uuid4())
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("origin") not in settings.origins:
            return error_response(request, DomainError(403, "FORBIDDEN", "허용되지 않은 요청 출처입니다."))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    def envelope(request, data):
        return {"data": jsonable_encoder(data), "meta": request_meta(request)}

    @app.get("/healthz")
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.post("/api/v1/demo/session", response_model=Envelope[SessionView])
    def switch_session(command: SessionCommand, request: Request, response: Response):
        with engine.begin() as connection:
            token = rotate_session(connection, settings, command.account_key, request.cookies.get(COOKIE_NAME))
            session = read_session(connection, settings, token)
        response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=settings.session_cookie_secure, samesite="lax", path="/")
        return envelope(request, session)

    @app.get("/api/v1/me", response_model=Envelope[SessionView])
    def me(request: Request, session=Depends(current_session)):
        result = envelope(request, session)
        result["meta"]["build"] = {"app_commit_sha": None, "working_tree_dirty": None,
                                   "agent_mode": settings.agent_mode, "search_mode": None}
        return result

    @app.get("/api/v1/equipment")
    def list_equipment(request: Request, session=Depends(current_session)):
        with engine.connect() as connection:
            rows = connection.execute(select(equipment.c.id, equipment.c.code, equipment.c.label, equipment.c.aliases)
                .where(equipment.c.site_id == session.site_id).order_by(equipment.c.code)).mappings().all()
        return envelope(request, {"items": [dict(r) for r in rows], "next_cursor": None})

    @app.get("/api/v1/shifts")
    def list_shifts(request: Request, session=Depends(current_session)):
        with engine.connect() as connection:
            rows = connection.execute(select(shifts).where(shifts.c.site_id == session.site_id).order_by(shifts.c.starts_at)).mappings().all()
            ids = [r["id"] for r in rows]
            pairs = connection.execute(select(shift_pairs).where(shift_pairs.c.from_shift_occurrence_id.in_(ids),
                shift_pairs.c.to_shift_occurrence_id.in_(ids))).mappings().all()
        return envelope(request, {"items": [dict(r) for r in rows], "next_cursor": None,
                                  "allowed_pairs": [dict(r) for r in pairs]})

    return app
