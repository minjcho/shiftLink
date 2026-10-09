#!/usr/bin/env python3
"""Export this project's visible Codex conversation text as local Markdown."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


PROJECT = Path(__file__).resolve().parents[1]
DESTINATION = PROJECT / "docs" / "history"
CONTEXT_PREFIXES = ("# AGENTS.md instructions", "<environment_context>")


def events(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # An active session can end with a partially written line.
                if not line.endswith("\n"):
                    return
                raise
            yield event


def visible_text(message):
    parts = []
    for item in message.get("content", []):
        if item.get("type") in ("input_text", "output_text", "text"):
            value = item.get("text", "")
            if message.get("role") == "user" and value.startswith(CONTEXT_PREFIXES):
                continue
            parts.append(value)
        elif item.get("type") == "input_image":
            url = item.get("image_url", "")
            if not isinstance(url, str) or url.startswith("data:"):
                url = "원본 Codex 대화의 이미지 첨부"
            parts.append(f"[이미지: {url}]")
        elif item.get("type") == "input_file":
            parts.append(f"[첨부 파일: {item.get('filename', '원본 Codex 대화 참조')}]")
    return "\n".join(parts)


def export(path, current_session, final_response):
    source = events(path)
    first = next(source, {})
    metadata = first.get("payload", {})
    if first.get("type") != "session_meta":
        return None
    if not metadata.get("cwd") or Path(metadata["cwd"]).resolve() != PROJECT:
        return None
    origin = metadata.get("source", {})
    if isinstance(origin, dict) and "subagent" in origin:
        return None
    session_id = str(UUID(metadata["id"]))
    started = metadata.get("timestamp", first.get("timestamp", ""))
    date = datetime.fromisoformat(started.replace("Z", "+00:00")).date()
    messages = []
    for event in source:
        message = event.get("payload", {})
        if event.get("type") != "response_item" or message.get("type") != "message":
            continue
        role = message.get("role")
        phase = message.get("channel") or message.get("phase")
        if role not in ("user", "assistant"):
            continue
        if role == "assistant" and phase not in (None, "commentary", "final", "final_answer"):
            continue
        text = visible_text(message)
        if text.strip():
            messages.append((event.get("timestamp", ""), role, phase, text))
    if final_response is not None and session_id == current_session:
        messages.append((datetime.now(timezone.utc).isoformat(), "assistant", "final", final_response))
    if not messages:
        return None
    lines = [
        "# Codex 대화 기록\n",
        f"- 세션: `{session_id}`\n- 프로젝트: `{PROJECT}`\n- 시작: {started}\n",
        "사용자와 Codex의 공개 대화 원문. 첨부 자료는 원본 대화 참조.\n",
    ]
    for timestamp, role, phase, text in messages:
        label = "사용자" if role == "user" else "Codex"
        if phase:
            label += f" ({phase})"
        lines.append(f"## {timestamp} · {label}\n\n{text}\n")
    target = DESTINATION / f"{date}-{session_id}.md"
    content = "\n".join(lines)
    if target.exists() and target.read_text(encoding="utf-8") == content:
        return target
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DESTINATION, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(target)
    finally:
        temporary_path.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Export every available root session for this project")
    parser.add_argument("--final-response", action="store_true", help="Read the imminent final response from stdin")
    args = parser.parse_args()
    current_session = os.environ.get("CODEX_THREAD_ID")
    if not args.all or args.final_response:
        if not current_session:
            parser.error("CODEX_THREAD_ID is required; use --all for an offline export")
        current_session = str(UUID(current_session))
    final_response = sys.stdin.read() if args.final_response else None
    if final_response is not None and not final_response.strip():
        parser.error("The final response on stdin must not be empty")
    codex_directory = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    pattern = "*.jsonl" if args.all else f"*{current_session}.jsonl"
    count = 0
    captured_current = False
    for directory in (codex_directory / "sessions", codex_directory / "archived_sessions"):
        for path in sorted(directory.rglob(pattern)):
            target = export(path, current_session, final_response)
            if target:
                count += 1
                captured_current |= target.stem.endswith(str(current_session))
                print(target.relative_to(PROJECT))
    if not count or (args.final_response and not captured_current):
        parser.error("No matching project session found; save the visible conversation manually")


if __name__ == "__main__":
    main()
