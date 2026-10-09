"""F0 maintenance process. F1 must register its handler before claiming jobs."""
import signal
import threading
from sqlalchemy import text

from .core.config import load_settings
from .core.database import make_engine
from .core.jobs import recover_exhausted


def main():
    settings = load_settings()
    engine = make_engine(settings)
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    # Dedicated session advisory lock enforces one maintenance worker per database.
    with engine.connect() as guard:
        if not guard.scalar(text("SELECT pg_try_advisory_lock(736245098)")):
            raise RuntimeError("Another ShiftLink worker already holds the worker lock")
        print("F0 worker ready: expired final-attempt recovery only; F1 handler not registered.", flush=True)
        try:
            while not stopped.is_set():
                # Losing this session loses the singleton lock: stop instead of
                # continuing recovery through a different pooled connection.
                guard.execute(text("SELECT 1"))
                recovered = recover_exhausted(engine, settings.job_max_attempts)
                if recovered:
                    print(f"Recovered {recovered} exhausted jobs.", flush=True)
                stopped.wait(settings.worker_poll_interval_seconds)
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(736245098)"))
    engine.dispose()


if __name__ == "__main__":
    main()
