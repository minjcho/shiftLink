"""Seal F3 condition entrypoint: real PostgreSQL HTTP tests plus required browser checks."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) != 2 or sys.argv[1] not in {f"AC-{i}" for i in range(1, 19)}:
        print("usage: python3 scripts/check_f3.py AC-<1..18>")
        return 64
    condition = sys.argv[1]
    number = int(condition.split("-")[1])
    if not (root / "apps/api/app/features/handovers/router.py").is_file():
        print("FAIL: F3 HTTP feature is absent on this revision.")
        return 1
    python = root / ".venv/bin/python"
    if not python.is_file():
        print("FAIL: verification environment missing; install requirements.lock in .venv")
        return 2
    env = {**os.environ, "PYTHONPATH": str(root / "apps/api")}
    result = subprocess.call([str(python), "-m", "pytest", "tests/handovers", "-q", "-m", f"ac{number}"], cwd=root, env=env)
    if result:
        return result
    if number in (1, 16, 17):
        browser = root / "scripts/f3_browser.py"
        if not browser.is_file():
            print(f"FAIL: {condition} requires the real-browser F3 check, which is absent.")
            return 1
        return subprocess.call([str(python), str(browser), condition], cwd=root, env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
