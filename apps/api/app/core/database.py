from contextlib import contextmanager
from sqlalchemy import create_engine, select, update, func

from .errors import DomainError
from .schema import incidents


def make_engine(settings):
    return create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True)


class Transaction:
    """One connection/commit boundary; adapters compose this rather than commit themselves."""
    def __init__(self, connection):
        self.connection = connection
        self.locked_incidents = {}
        self.bumped = set()

    def lock_incident(self, incident_id, site_id=None):
        statement = select(incidents).where(incidents.c.id == incident_id)
        if site_id is not None:
            statement = statement.where(incidents.c.site_id == site_id)
        row = self.connection.execute(statement.with_for_update()).mappings().one_or_none()
        if row is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "사건을 찾을 수 없습니다.")
        self.locked_incidents[incident_id] = row
        return row

    def bump_incident(self, incident_id, expected_version, **changes):
        if incident_id not in self.locked_incidents:
            raise RuntimeError("Lock Incident before related rows or version changes")
        if incident_id in self.bumped:
            raise RuntimeError("Incident version may increase only once per transaction")
        if {"id", "site_id", "version"} & changes.keys():
            raise ValueError("Identity and version are managed by the transaction")
        row = self.connection.execute(update(incidents).where(
            incidents.c.id == incident_id, incidents.c.version == expected_version).values(
                **changes, version=expected_version + 1, updated_at=func.clock_timestamp()).returning(incidents)).mappings().one_or_none()
        if row is None:
            raise DomainError(409, "VERSION_CONFLICT", "사건이 변경됐습니다.",
                current_version=self.locked_incidents[incident_id]["version"], details={"target": "incident"})
        self.bumped.add(incident_id)
        return row


@contextmanager
def transaction(engine):
    with engine.begin() as connection:
        yield Transaction(connection)
