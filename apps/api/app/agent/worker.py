"""One separate synchronous DB worker. API requests never launch model processes."""
from __future__ import annotations

import importlib.metadata
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from app.core.config import Settings
from app.core.db import create_session_factory
from app.core.errors import DomainError
from app.core.ports import FeaturePorts
from .finalizer import DecisionRejected, finalize
from .jobs import LostLease, claim_job, finish_failure, prepare_run, recover_exhausted
from .runner import OpenAIResponsesTransport, RunLimits, run_agent
from .tools import ToolExecutor


def runtime_metadata(settings: Settings, adapter) -> dict:
    public = {name: getattr(settings, name) for name in (
        "agent_run_deadline_seconds", "agent_max_model_calls", "agent_max_tool_calls",
        "agent_max_output_tokens", "search_max_chunks", "search_max_chunk_chars",
        "worker_poll_interval_seconds", "job_lease_seconds", "job_max_attempts", "dataset_id",
        "app_timezone",
    )}
    public.update({"mode": adapter.mode, "model_id": adapter.model_id, "dataset_version": "0.3.0"})
    digest = hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    app_sha = os.environ.get("APP_COMMIT_SHA") or None
    dirty_value = os.environ.get("WORKING_TREE_DIRTY", "").lower()
    dirty = {"true": True, "false": False}.get(dirty_value)
    project = Path(__file__).resolve().parents[4]
    try:
        if app_sha is None:
            result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, capture_output=True,
                                    text=True, timeout=2, check=True)
            app_sha = result.stdout.strip()
        if dirty is None:
            result = subprocess.run(["git", "status", "--porcelain"], cwd=project, capture_output=True,
                                    text=True, timeout=2, check=True)
            dirty = bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {"app_sha": app_sha, "dirty": dirty, "run_group_id": str(uuid4()), "dataset_version": "0.3.0",
            "settings_id": f"sha256:{digest}", "sdk_version": importlib.metadata.version("openai")}


def run_once(session_factory, settings: Settings, ports: FeaturePorts, model_adapter=None, *, metadata=None):
    if model_adapter is None:
        settings.validate(worker=True)
        if settings.agent_mode != "live":
            raise ValueError("fake/replay requires an explicit injected adapter")
        from openai import OpenAI
        model_adapter = OpenAIResponsesTransport(
            client=OpenAI(api_key=settings.openai_api_key, max_retries=0), model_id=settings.openai_agent_model)
    else:
        settings.validate(worker=False)
    recover_exhausted(session_factory, max_attempts=settings.job_max_attempts)
    run_metadata = {**runtime_metadata(settings, model_adapter),
                    **(metadata or {}), **getattr(model_adapter, "replay_metadata", {})}
    start = time.monotonic()
    identity = claim_job(session_factory, mode=model_adapter.mode, model_id=model_adapter.model_id,
                         lease_seconds=settings.job_lease_seconds, max_attempts=settings.job_max_attempts,
                         metadata=run_metadata)
    if identity is None:
        return None
    execution = None
    try:
        context = prepare_run(session_factory, identity, ports)
        identity = context.identity
        executor = ToolExecutor(session_factory, context, max_chunks=settings.search_max_chunks,
                                max_chunk_chars=settings.search_max_chunk_chars,
                                deadline_at=start + settings.agent_run_deadline_seconds)
        execution = run_agent(
            context=context.payload, transport=model_adapter, execute_tool=executor,
            limits=RunLimits(settings.agent_run_deadline_seconds, settings.agent_max_model_calls,
                             settings.agent_max_tool_calls, settings.agent_max_output_tokens), started_at=start)
        if execution.error is not None:
            applied = finish_failure(session_factory, identity, execution.error, execution=execution)
            return {"status": "FAILED" if applied else "LEASE_LOST", "job_id": identity.job_id,
                    "run_id": identity.run_id, "error_code": execution.error["code"]}
        return finalize(session_factory, identity, execution, ports)
    except LostLease:
        return {"status": "LEASE_LOST", "job_id": identity.job_id, "run_id": identity.run_id}
    except (DecisionRejected, DomainError) as exc:
        error = {"code": exc.code, "message": "The server rejected the investigation result or required feature boundary",
                 "retryable": bool(getattr(exc, "retryable", False))}
        if isinstance(exc, DecisionRejected) and exc.details is not None:
            error["details"] = exc.details
    except Exception:
        error = {"code": "EXECUTION_ERROR", "message": "The investigation could not be finalized", "retryable": True}
    applied = finish_failure(session_factory, identity, error, execution=execution)
    return {"status": "FAILED" if applied else "LEASE_LOST", "job_id": identity.job_id,
            "run_id": identity.run_id, "error_code": error["code"]}


def main():
    settings = Settings.from_env()
    settings.validate(worker=True)
    factory = create_session_factory(settings.database_url)
    ports = FeaturePorts()
    while True:
        result = run_once(factory, settings, ports)
        if result is None:
            time.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    main()
