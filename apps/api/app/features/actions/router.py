"""Mount with F0's authenticated, Origin-checked principal dependency.

No default dependency or fallback session is supplied: missing wiring fails at setup.
F0 also installs the app-wide RequestValidationError envelope handler.
"""

from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from .commands import ApprovalCommand, CompletionCommand, StartCommand
from .errors import ActionError
from .models import Principal
from .responses import ApprovalResult, CompletionResult, StartResult, SuccessEnvelope
from .service import ActionApplication


def create_actions_router(application: ActionApplication, principal_dependency: Callable,
                          meta_dependency: Callable) -> APIRouter:
    router = APIRouter(prefix="/actions", tags=["actions"])

    def invoke(principal, meta, action_id, key, command):
        try:
            response = application.execute(principal, action_id, key, command, meta)
        except ActionError as exc:
            return JSONResponse(status_code=exc.status, content=exc.envelope(meta))
        return JSONResponse(status_code=response.status, content=response.body,
                            headers={"Idempotent-Replayed": "true"} if response.replayed else {})

    @router.post("/{action_id}/approval-decisions", response_model=SuccessEnvelope[ApprovalResult])
    def approve(action_id: UUID, command: ApprovalCommand,
                principal: Principal = Depends(principal_dependency),
                meta: dict = Depends(meta_dependency),
                key: str = Header(alias="Idempotency-Key", min_length=1)):
        return invoke(principal, meta, action_id, key, command)

    @router.post("/{action_id}/start", response_model=SuccessEnvelope[StartResult])
    def start(action_id: UUID, command: StartCommand,
              principal: Principal = Depends(principal_dependency),
              meta: dict = Depends(meta_dependency),
              key: str = Header(alias="Idempotency-Key", min_length=1)):
        return invoke(principal, meta, action_id, key, command)

    @router.post("/{action_id}/completion", response_model=SuccessEnvelope[CompletionResult])
    def complete(action_id: UUID, command: CompletionCommand,
                 principal: Principal = Depends(principal_dependency),
                 meta: dict = Depends(meta_dependency),
                 key: str = Header(alias="Idempotency-Key", min_length=1)):
        return invoke(principal, meta, action_id, key, command)

    return router
