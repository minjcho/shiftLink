from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import hmac
import secrets

from sqlalchemy import delete, select, func

from .errors import DomainError
from .models import SessionToken, Shift, ShiftAssignment, User
from .contracts import SessionView

COOKIE_NAME = "shiftlink_session"


@dataclass(frozen=True)
class Principal:
    user_id: str
    site_id: str
    role: str
    display_name: str
    shift_occurrence_id: str | None = None
    duties: tuple[str, ...] = ()


def token_hash(token, settings):
    return hmac.new(settings.session_secret.encode(), token.encode(), sha256).hexdigest()


def check_origin(request):
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise DomainError(403, "FORBIDDEN", "허용되지 않은 요청 출처입니다.")


def principal_from_request(request):
    settings = request.app.state.settings
    raw = request.cookies.get(COOKIE_NAME)
    if not raw or len(raw) > 200:
        raise DomainError(401, "UNAUTHENTICATED", "세션을 선택해 주세요.")
    with request.app.state.session_factory() as tx:
        row = tx.execute(select(User, SessionToken.shift_occurrence_id)
            .join(SessionToken, SessionToken.user_id == User.id)
            .join(Shift, Shift.id == SessionToken.shift_occurrence_id).where(
                SessionToken.token_hash == token_hash(raw, settings), SessionToken.expires_at > func.clock_timestamp(),
                User.enabled.is_(True), Shift.site_id == User.site_id)).first()
        if row is None:
            raise DomainError(401, "UNAUTHENTICATED", "유효한 세션이 필요합니다.")
        user, shift_id = row
        duties = tuple(tx.scalars(select(ShiftAssignment.duty).where(
            ShiftAssignment.user_id == user.id, ShiftAssignment.shift_occurrence_id == shift_id)))
        if not duties:
            raise DomainError(403, "FORBIDDEN", "교대 배정을 확인할 수 없습니다.")
        return Principal(user.id, user.site_id, user.role, user.display_name, shift_id, duties)


def rotate_demo_session(request, account_key):
    settings = request.app.state.settings
    if not settings.demo_account_switch_enabled:
        raise DomainError(404, "RESOURCE_NOT_FOUND", "대상을 찾을 수 없습니다.")
    check_origin(request)
    with request.app.state.session_factory.begin() as tx:
        user = tx.scalar(select(User).where(User.account_key == account_key, User.enabled.is_(True)))
        if user is None:
            raise DomainError(403, "FORBIDDEN", "허용된 데모 계정이 아닙니다.")
        assignment = tx.execute(select(ShiftAssignment, Shift)
            .join(Shift, Shift.id == ShiftAssignment.shift_occurrence_id)
            .where(ShiftAssignment.user_id == user.id, Shift.site_id == user.site_id)
            .order_by(Shift.active.desc(), Shift.starts_at, Shift.id)).first()
        if assignment is None:
            raise DomainError(422, "SHIFT_ASSIGNMENT_MISSING", "교대 배정이 없습니다.")
        old = request.cookies.get(COOKIE_NAME)
        if old:
            tx.execute(delete(SessionToken).where(SessionToken.token_hash == token_hash(old, settings)))
        raw = secrets.token_urlsafe(32)
        tx.add(SessionToken(user_id=user.id, token_hash=token_hash(raw, settings),
                            shift_occurrence_id=assignment[1].id,
                            expires_at=func.clock_timestamp() + timedelta(hours=12)))
        principal = Principal(user.id, user.site_id, user.role, user.display_name,
                              assignment[1].id, (assignment[0].duty,))
        return raw, principal_data(tx, principal)


def require_owner(principal, incident):
    if principal.role != "supervisor" or principal.user_id != incident.owner_id:
        raise DomainError(403, "FORBIDDEN", "현재 책임자만 실행할 수 있습니다.")


def current_shift(tx, principal):
    return tx.scalar(select(Shift).where(Shift.site_id == principal.site_id, Shift.active.is_(True)))


def principal_data(tx, principal):
    return SessionView(user_id=principal.user_id, display_name=principal.display_name, role=principal.role,
                       site_id=principal.site_id, shift_occurrence_id=principal.shift_occurrence_id,
                       duties=list(principal.duties)).model_dump(mode="json")
