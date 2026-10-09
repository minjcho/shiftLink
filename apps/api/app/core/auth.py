from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import hmac
import secrets

from sqlalchemy import delete, select

from .errors import DomainError
from .models import SessionToken, Shift, ShiftAssignment, User, utcnow

COOKIE_NAME = "shiftlink_session"


@dataclass(frozen=True)
class Principal:
    user_id: str
    site_id: str
    role: str
    display_name: str


def token_hash(token, settings):
    return hmac.new(settings.session_secret.encode(), token.encode(), sha256).hexdigest()


def check_origin(request):
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise DomainError(403, "FORBIDDEN", "허용되지 않은 요청 출처입니다.")


def principal_from_request(request):
    settings = request.app.state.settings
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise DomainError(401, "UNAUTHENTICATED", "세션을 선택해 주세요.")
    with request.app.state.session_factory() as tx:
        row = tx.scalar(select(User).join(SessionToken, SessionToken.user_id == User.id).where(
            SessionToken.token_hash == token_hash(raw, settings), SessionToken.expires_at > utcnow(), User.enabled.is_(True)))
        if row is None:
            raise DomainError(401, "UNAUTHENTICATED", "유효한 세션이 필요합니다.")
        return Principal(row.id, row.site_id, row.role, row.display_name)


def rotate_demo_session(request, account_key):
    settings = request.app.state.settings
    if not settings.demo_account_switch_enabled:
        raise DomainError(404, "RESOURCE_NOT_FOUND", "대상을 찾을 수 없습니다.")
    check_origin(request)
    with request.app.state.session_factory.begin() as tx:
        user = tx.scalar(select(User).where(User.account_key == account_key, User.enabled.is_(True)))
        if user is None:
            raise DomainError(403, "FORBIDDEN", "허용된 데모 계정이 아닙니다.")
        old = request.cookies.get(COOKIE_NAME)
        if old:
            tx.execute(delete(SessionToken).where(SessionToken.token_hash == token_hash(old, settings)))
        raw = secrets.token_urlsafe(32)
        tx.add(SessionToken(user_id=user.id, token_hash=token_hash(raw, settings), expires_at=utcnow() + timedelta(hours=12)))
        return raw, {"user_id": user.id, "display_name": user.display_name, "role": user.role, "site_id": user.site_id}


def require_owner(principal, incident):
    if principal.role != "supervisor" or principal.user_id != incident.owner_id:
        raise DomainError(403, "FORBIDDEN", "현재 책임자만 실행할 수 있습니다.")


def current_shift(tx, principal):
    return tx.scalar(select(Shift).where(Shift.site_id == principal.site_id, Shift.active.is_(True)))


def principal_data(tx, principal):
    assignment = tx.execute(select(ShiftAssignment, Shift).join(Shift, Shift.id == ShiftAssignment.shift_occurrence_id)
        .where(ShiftAssignment.user_id == principal.user_id, Shift.site_id == principal.site_id)
        .order_by(Shift.active.desc(), Shift.starts_at)).first()
    return {"user_id": principal.user_id, "display_name": principal.display_name, "role": principal.role,
            "site_id": principal.site_id, "shift_occurrence_id": assignment[1].id if assignment else None,
            "duties": [assignment[0].duty] if assignment else []}
