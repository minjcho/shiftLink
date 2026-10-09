import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert

from .errors import DomainError
from .schema import command_receipts as receipts


def fingerprint(method: str, canonical_route: str, body: dict) -> str:
    payload = json.dumps({"method": method.upper(), "route": canonical_route, "body": body},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ReceiptResponse:
    status: int
    body: dict


def scope(principal, key):
    return (receipts.c.site_id == principal.site_id) & (receipts.c.actor_id == principal.user_id) & (receipts.c.idempotency_key == key)


def reserve_command(connection, principal, key, payload_hash):
    if not key.strip() or len(key) > 200:
        raise DomainError(422, "VALIDATION_ERROR", "유효한 Idempotency-Key가 필요합니다.")
    # Transaction-scoped, nonblocking lock gives explicit in-flight response, not a long insert wait.
    lock_bytes = hashlib.sha256(f"{principal.site_id}:{principal.user_id}:{key}".encode()).digest()[:8]
    lock_id = int.from_bytes(lock_bytes, "big", signed=True)
    if not connection.scalar(select(func.pg_try_advisory_xact_lock(lock_id))):
        raise DomainError(409, "COMMAND_IN_PROGRESS", "같은 요청을 처리 중입니다.")
    row = connection.execute(select(receipts).where(scope(principal, key))).mappings().one_or_none()
    if row:
        if row["payload_hash"] != payload_hash:
            raise DomainError(409, "IDEMPOTENCY_CONFLICT", "같은 요청 키에 다른 입력이 전달됐습니다.")
        if row["status"] != "COMPLETED":
            raise DomainError(409, "COMMAND_IN_PROGRESS", "같은 요청을 처리 중입니다.")
        return ReceiptResponse(row["http_status"], row["response_json"])
    connection.execute(insert(receipts).values(site_id=principal.site_id, actor_id=principal.user_id,
        idempotency_key=key, payload_hash=payload_hash, status="RUNNING"))
    return None


def finish_command(connection, principal, key, response: ReceiptResponse):
    updated = connection.execute(update(receipts).where(scope(principal, key), receipts.c.status == "RUNNING")
        .values(status="COMPLETED", http_status=response.status, response_json=response.body))
    if updated.rowcount != 1:
        raise RuntimeError("Command receipt must be reserved in this transaction")
