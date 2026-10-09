from uuid import UUID

from fastapi import Query, Request

from app.core.auth import principal_from_request
from .schemas import VerificationBody
from . import service


def register_routes(app, command, with_meta):
    @app.post("/api/v1/incidents/{incident_id}/verification")
    def verify(incident_id: UUID, request: Request, body: VerificationBody):
        return command(request, body, lambda tx, actor: service.verify(
            tx, actor, str(incident_id), body, app.state.ports))

    @app.get("/api/v1/cases")
    def cases(request: Request, incident_id: UUID | None = None,
              cursor: str | None = Query(default=None, max_length=2048),
              limit: int = Query(default=20, ge=1, le=100)):
        principal = principal_from_request(request)
        with app.state.session_factory() as tx:
            return with_meta(request, {"data": service.list_cases(tx, principal,
                incident_id=str(incident_id) if incident_id else None, cursor=cursor, limit=limit)})
