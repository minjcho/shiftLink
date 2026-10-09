"""Seal condition entrypoint. Each condition executes its behavioral tests."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) != 2 or sys.argv[1] not in {f"AC-{i}" for i in range(1, 35)}:
        print("usage: python3 scripts/check_f1.py AC-<1..34>")
        return 64
    # On Seal's base revision, no executable F1 exists. No synthetic pass or skip.
    if not (root / "apps/api/app/main.py").is_file():
        print("FAIL: F1 HTTP application is absent on this revision.")
        return 1
    number = int(sys.argv[1].split("-")[1])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "apps/api")
    if number in (30, 31):
        cmd = ["npm", "run", "unit:ac", "--", str(number)]
        return subprocess.call(cmd, cwd=root / "apps/web", env=env)
    python = root / ".venv/bin/python"
    if not python.exists():
        print("Verification environment missing: install requirements.lock in .venv")
        return 2
    if number == 33:
        return subprocess.call([str(python), "scripts/f1_browser.py"], cwd=root, env=env)
    return subprocess.call(
        [str(python), "-m", "pytest", "-q", "-m", f"ac{number}"],
        cwd=root, env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
