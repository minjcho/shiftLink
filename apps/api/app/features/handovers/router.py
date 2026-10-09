from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.auth import principal_from_request
from app.features.handovers import service
from app.features.handovers.schemas import AcknowledgeBody, CreateHandoverBody


def register(app, *, command, with_meta):
    """Wire F3 through F0's session, Origin, receipt and transaction wrapper."""
    router = APIRouter(prefix="/api/v1/handovers", tags=["handovers"])

    @router.post("")
    def create(request: Request, body: CreateHandoverBody):
        return command(request, body, lambda tx, actor: service.create_or_refresh(tx, actor, body))

    @router.get("/{handover_id}")
    def read(handover_id: UUID, request: Request, item_id: UUID | None = None,
             revision: int | None = Query(default=None, ge=1)):
        actor = principal_from_request(request)
        with app.state.session_factory() as tx:
            data = service.read_handover(tx, actor, str(handover_id),
                item_id=str(item_id) if item_id else None, revision=revision)
            return with_meta(request, {"data": data})

    @router.post("/{handover_id}/items/{item_id}/ack")
    def acknowledge(handover_id: UUID, item_id: UUID, request: Request, body: AcknowledgeBody):
        return command(request, body, lambda tx, actor: service.acknowledge(
            tx, actor, str(handover_id), str(item_id), body))

    app.include_router(router)
