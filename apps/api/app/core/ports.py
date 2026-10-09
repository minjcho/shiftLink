from dataclasses import dataclass
from typing import Callable
from sqlalchemy import select

from .errors import DomainError
from .models import HandoverItem


def unavailable(feature):
    return DomainError(503, "SERVICE_UNAVAILABLE", f"{feature} 연결이 아직 제공되지 않았습니다.",
                       details={"feature": feature}, retryable=False)


@dataclass
class FeaturePorts:
    """Explicit caller-owned transaction adapters, never fake product success."""
    action_finalizer: Callable | None = None
    readiness_evaluator: Callable | None = None
    handover_refresher: Callable | None = None

    def finalize_action_proposal(self, tx, **kwargs):
        if self.action_finalizer is None:
            raise unavailable("F2")
        return self.action_finalizer(tx, **kwargs)

    def evaluate_resolution_readiness(self, tx, *, incident):
        if self.readiness_evaluator is None:
            raise unavailable("F4")
        return self.readiness_evaluator(tx, incident=incident)

    def refresh_handover_items(self, tx, *, incident, event):
        if self.handover_refresher is not None:
            return self.handover_refresher(tx, incident=incident, event=event)
        if tx.scalar(select(HandoverItem.id).where(HandoverItem.incident_id == incident.id).limit(1)):
            raise unavailable("F3")
        return None
