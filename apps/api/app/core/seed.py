"""Repeatable reference seed only; never resets incidents or creates successful work."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert

from . import schema as s


def uid(number):
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


def seed(connection):
    def add(table, rows):
        for row in rows:
            connection.execute(insert(table).values(**row).on_conflict_do_nothing())
    add(s.sites, [{"id": uid(1), "name": "SITE-DEMO · 합성 제조사업장"}])
    add(s.users, [{"id": uid(n), "site_id": uid(1), "account_key": key, "display_name": name, "role": role}
        for n, key, name, role in [(201, "reporter", "작업자", "worker"), (202, "maintainer", "정비 담당자", "worker"),
            (203, "outgoing_supervisor", "출발 책임자", "supervisor"), (204, "incoming_supervisor", "수신 책임자", "supervisor")]])
    add(s.shifts, [{"id": uid(n), "site_id": uid(1), "label": label, "supervisor_id": uid(owner),
        "starts_at": datetime(2026, 10, 9, start, tzinfo=UTC), "ends_at": datetime(2026, 10, 9, end, tzinfo=UTC)}
        for n, label, owner, start, end in [(301, "SHIFT-20261009-A", 203, 0, 4), (302, "SHIFT-20261009-B", 204, 4, 8)]])
    add(s.shift_assignments, [{"shift_occurrence_id": uid(shift), "user_id": uid(user), "duty": duty}
        for shift, user, duty in [(301, 201, "OPERATOR"), (301, 202, "MAINTENANCE"), (301, 203, "SUPERVISOR"),
                                  (302, 201, "OPERATOR"), (302, 202, "MAINTENANCE"), (302, 204, "SUPERVISOR")]])
    add(s.shift_pairs, [{"from_shift_occurrence_id": uid(301), "to_shift_occurrence_id": uid(302)}])
    add(s.equipment, [{"id": uid(n), "site_id": uid(1), "code": code, "label": label,
                      "aliases": aliases, "default_maintainer_id": uid(202)}
        for n, code, label, aliases in [(103, "CV-03", "3번 이송 설비", ["3호기"]), (102, "CV-02", "2번 이송 설비", ["2호기"])]])


if __name__ == "__main__":
    from .config import load_settings
    from .database import make_engine
    settings = load_settings()
    if settings.app_env != "development":
        raise RuntimeError("Reference demo seed is only allowed in development")
    engine = make_engine(settings)
    with engine.begin() as connection:
        seed(connection)
    engine.dispose()
    print("Reference seed ready: 4 accounts, 2 equipment, 2 shifts; no incidents created.")
