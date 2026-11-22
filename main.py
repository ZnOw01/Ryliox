#!/usr/bin/env python3
"""Ryliox — Main entry point."""

from __future__ import annotations

import argparse
import sys

import config
from web.server import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Ryliox — O'Reilly book downloader")
    parser.add_argument("--host", default=config.SETTINGS.server.host, help="Server host")
    parser.add_argument(
        "--port",
        type=int,
        default=config.SETTINGS.server.port,
        help="Server port",
    )
    args = parser.parse_args()

    print(f"Ryliox — open http://{args.host}:{args.port} in your browser (Ctrl+C to stop)")
    try:
        run_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\nServer stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
