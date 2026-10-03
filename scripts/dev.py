"""Local development setup and checks. Never contact providers or print secrets."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PROVIDER_SETTINGS = ("HELIUS_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def create_env(root: Path) -> bool:
    """Create private placeholders once; preserve all existing local configuration."""
    contents = (root / ".env.example").read_bytes()
    try:
        descriptor = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(contents)
    return True


def check_versions(root: Path) -> None:
    pins = json.loads((root / "scripts/toolchain.json").read_text())
    if sys.version.split()[0] != pins["python"]:
        raise RuntimeError("Python version mismatch; rebuild the devcontainer.")
    print(f"python {pins['python']}")
    for tool in ("node", "npm", "uv", "psql"):
        result = subprocess.run([tool, "--version"], capture_output=True, text=True, check=True)
        match = re.search(r"\d+\.\d+(?:\.\d+)?", result.stdout)
        if not match or match.group() != pins[tool]:
            raise RuntimeError(f"{tool} version mismatch; rebuild the devcontainer.")
        print(f"{tool} {pins[tool]}")


def provider_check(root: Path) -> int:
    """Validate presence only. Do not source shell code or show configuration values."""
    configured = {}
    if (root / ".env").is_file():
        for line in (root / ".env").read_text().splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key in REQUIRED_PROVIDER_SETTINGS:
                configured[key] = value.strip().strip("\"'")
    missing = [
        key
        for key in REQUIRED_PROVIDER_SETTINGS
        if not os.environ.get(key, configured.get(key, "")).strip()
    ]
    if missing:
        print("Missing optional integration configuration: " + ", ".join(missing))
        print("Development setup works without these settings. No live request was made.")
        return 2
    print(
        "Configuration is present. Source qualification is still required; "
        "no live request was made."
    )
    return 0


def doctor(root: Path) -> None:
    check_versions(root)
    if os.getuid() == 0:
        raise RuntimeError("Use the non-root developer account.")
    with tempfile.TemporaryFile(dir=root) as stream:
        stream.write(b"workspace-write-check")
    print("Non-root workspace write check passed.")
    # A real SQL query proves authentication and connectivity, beyond pg_isready.
    subprocess.run(
        ["psql", "--no-psqlrc", "--set=ON_ERROR_STOP=1", "--command=SELECT 1;"],
        check=True,
        capture_output=True,
    )
    print("Development PostgreSQL connection passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "doctor", "provider-check"))
    args = parser.parse_args()
    try:
        if args.command == "provider-check":
            return provider_check(ROOT)
        if args.command == "doctor":
            doctor(ROOT)
            return 0
        check_versions(ROOT)
        subprocess.run(["uv", "sync", "--locked"], cwd=ROOT, check=True)
        subprocess.run(
            ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=ROOT, check=True
        )
        created = create_env(ROOT)
        print("Created private .env placeholders." if created else "Preserved existing .env.")
        print("Development tools installed. Run make doctor; application work begins in WO-003.")
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, subprocess.CalledProcessError):
        # Do not echo command output: it may include a local database connection string.
        print(
            "Development check failed. Use the pinned devcontainer, verify workspace permissions "
            "and database health, and retry. See docs/development.md.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
