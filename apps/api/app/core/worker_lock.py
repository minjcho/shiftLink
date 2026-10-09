"""A dedicated PostgreSQL connection owns the single worker slot."""
from contextlib import contextmanager

from sqlalchemy import text

WORKER_LOCK = 736245098


@contextmanager
def single_worker(engine):
    # AUTOCOMMIT avoids a long-running idle transaction while the model runs.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as guard:
        if not guard.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": WORKER_LOCK}):
            raise RuntimeError("Another ShiftLink worker already holds the worker lock")
        backend_pid = guard.scalar(text("SELECT pg_backend_pid()"))

        def check():
            # A reconnected pool connection does not own the original lock.
            if guard.scalar(text("SELECT pg_backend_pid()")) != backend_pid:
                raise RuntimeError("The worker lock connection was lost")

        try:
            yield check
        finally:
            if not guard.invalidated:
                guard.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": WORKER_LOCK})
