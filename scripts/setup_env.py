"""Create local demo secrets without overwriting an existing environment file."""
import argparse
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=root / ".env")
args = parser.parse_args()
password = secrets.token_urlsafe(32)
content = (root / ".env.example").read_text()
content = content.replace("SESSION_SECRET=\n", "SESSION_SECRET=" + secrets.token_urlsafe(48) + "\n")
content = content.replace("replace_for_local_development", password)
try:
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(content)
except FileExistsError:
    raise SystemExit("Environment file already exists; preserved. Use a different --output path or edit it locally.")
print("Local environment created. Values are not printed. Do not commit the file.")
