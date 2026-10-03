"""Supervise the three local development processes and stop their process groups together."""

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress

from wallet_observer.logging import configure_logging, event
from wallet_observer.settings import ConfigurationError, load_settings


def main():
    configure_logging("dev")
    try:
        load_settings()
    except ConfigurationError as error:
        event("configuration_invalid", safe_configuration_error=str(error))
        return 2
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    children = []
    commands = [
        [sys.executable, "-m", "wallet_observer", "api", "--host", "0.0.0.0"],
        [sys.executable, "-m", "wallet_observer", "worker"],
        ["npm", "run", "dev", "--workspace", "frontend"],
    ]
    try:
        for command in commands:
            environment = os.environ.copy()
            if command[0] == "npm":
                for key in (
                    "DATABASE_URL",
                    "HELIUS_API_KEY",
                    "TELEGRAM_BOT_TOKEN",
                    "TELEGRAM_CHAT_ID",
                ):
                    environment.pop(key, None)
            children.append(subprocess.Popen(command, start_new_session=True, env=environment))
        while not stopping:
            if any(child.poll() is not None for child in children):
                event("service_failed")
                return 1
            time.sleep(0.2)
        return 0
    except OSError:
        event("service_failed")
        return 1
    finally:
        for child in children:
            # A child leader can exit before its descendants. Signal the whole group.
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass
        for child in children:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
