"""Run: python -m qwennews.dashboard_api --host 127.0.0.1 --port 8765"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="QwenNews read-only dashboard API")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(
            "Refusing to bind non-loopback host. Dashboard API is local-only "
            f"(got {args.host!r})."
        )
    uvicorn.run(
        "qwennews.dashboard_api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
