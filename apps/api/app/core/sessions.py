import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select, delete, insert, func

from .contracts import SessionView
from .errors import DomainError
from .schema import users, sites, sessions, shifts, shift_assignments

COOKIE_NAME = "shiftlink_session"
SESSION_SECONDS = 8 * 60 * 60
ACCOUNT_SHIFTS = {"reporter": 301, "maintainer": 301, "outgoing_supervisor": 301, "incoming_supervisor": 302}


def token_hash(settings, token):
    return hmac.new(settings.session_secret.get_secret_value().encode(), token.encode(), hashlib.sha256).hexdigest()


def rotate_session(connection, settings, account_key, old_token):
    if not settings.demo_account_switch_enabled:
        raise DomainError(404, "RESOURCE_NOT_FOUND", "세션 전환을 사용할 수 없습니다.")
    from .seed import uid
    user = connection.execute(select(users).where(users.c.account_key == account_key, users.c.enabled.is_(True))).mappings().one_or_none()
    if user is None or account_key not in ACCOUNT_SHIFTS:
        raise DomainError(422, "VALIDATION_ERROR", "허용되지 않은 계정입니다.")
    shift_id = uid(ACCOUNT_SHIFTS[account_key])
    assignment = connection.scalar(select(shift_assignments.c.user_id).join(shifts,
        shifts.c.id == shift_assignments.c.shift_occurrence_id).where(
            shift_assignments.c.user_id == user["id"], shifts.c.id == shift_id, shifts.c.site_id == user["site_id"]))
    if assignment is None:
        raise DomainError(422, "SHIFT_ASSIGNMENT_MISSING", "교대 배정이 없습니다.")
    if old_token:
        connection.execute(delete(sessions).where(sessions.c.token_hash == token_hash(settings, old_token)))
    token = secrets.token_urlsafe(32)
    connection.execute(insert(sessions).values(token_hash=token_hash(settings, token), user_id=user["id"],
        shift_occurrence_id=shift_id, expires_at=func.clock_timestamp() + timedelta(seconds=SESSION_SECONDS)))
    return token


def read_session(connection, settings, token):
    if not token or len(token) > 200:
        raise DomainError(401, "UNAUTHENTICATED", "계정을 선택해 주세요.")
    row = connection.execute(select(users, sites.c.name.label("site_name"), sessions.c.shift_occurrence_id)
        .join(sessions, sessions.c.user_id == users.c.id).join(sites, sites.c.id == users.c.site_id)
        .join(shifts, shifts.c.id == sessions.c.shift_occurrence_id)
        .where(sessions.c.token_hash == token_hash(settings, token), sessions.c.expires_at > func.clock_timestamp(),
               users.c.enabled.is_(True), shifts.c.site_id == users.c.site_id)).mappings().one_or_none()
    if row is None:
        raise DomainError(401, "UNAUTHENTICATED", "세션이 만료됐습니다. 계정을 다시 선택해 주세요.")
    duties = list(connection.scalars(select(shift_assignments.c.duty).where(
        shift_assignments.c.shift_occurrence_id == row["shift_occurrence_id"], shift_assignments.c.user_id == row["id"])))
    if not duties:
        raise DomainError(403, "FORBIDDEN", "교대 배정을 확인할 수 없습니다.")
    return SessionView(user_id=row["id"], site_id=row["site_id"], role=row["role"], display_name=row["display_name"],
        site_name=row["site_name"], shift_occurrence_id=row["shift_occurrence_id"], duties=duties)


def current_session(request: Request):
    with request.app.state.engine.connect() as connection:
        return read_session(connection, request.app.state.settings, request.cookies.get(COOKIE_NAME))
