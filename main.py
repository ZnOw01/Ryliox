#!/usr/bin/env python3
"""Ryliox — Main entry point."""

from __future__ import annotations

import argparse
import logging
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

    logging.basicConfig(
        level=config.SETTINGS.logging.level,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    print("=" * 50)
    print("  Ryliox")
    print("=" * 50)
    print(f"\n  Open http://{args.host}:{args.port} in your browser\n")
    print("  Press Ctrl+C to stop\n")
    print("=" * 50)

    try:
        run_server(host=args.host, port=args.port)
        return 0
    except KeyboardInterrupt:
        print("\n  Server stopped gracefully. Goodbye!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
