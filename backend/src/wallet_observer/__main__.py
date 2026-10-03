"""Start one API or worker process, or validate configuration without network calls."""

import argparse

import uvicorn

from wallet_observer.api import create_app
from wallet_observer.logging import configure_logging, event
from wallet_observer.settings import ConfigurationError, load_settings
from wallet_observer.worker import create_worker_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("api", "worker", "config-check"))
    parser.add_argument("--host", choices=("127.0.0.1", "0.0.0.0"), default="127.0.0.1")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    configure_logging(args.service)
    try:
        settings = load_settings()
    except ConfigurationError as error:
        event("configuration_invalid", safe_configuration_error=str(error))
        return 2
    if args.service == "config-check":
        event("configuration_valid", mode=settings.app_mode)
        return 0
    if args.port is not None and not 1 <= args.port <= 65535:
        event("configuration_invalid", safe_configuration_error="PORT: must be between 1 and 65535")
        return 2
    app = create_app(settings) if args.service == "api" else create_worker_app(settings)
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port or (8000 if args.service == "api" else 8001),
            log_config=None,
            access_log=False,
            server_header=False,
        )
    except Exception:
        event("service_failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
