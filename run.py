#!/usr/bin/env python3
"""Monetize Compute. Stake it, start it, watch it earn or die.

    python3 run.py [--stake 5.0] [--cycle 60] [--port 8901]
"""

import argparse
import os
from pathlib import Path


def load_env(path=Path(__file__).resolve().parent / ".env"):
    """Minimal .env loader, stdlib only. Real environment always wins:
    a deployed override must beat a file on disk. Must run before mc
    imports; the model ladder is priced at import time."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env()

from mc.loop import Agent  # noqa: E402  (env must load first)
from mc.server import serve  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stake", type=float, default=5.0, help="starting wallet, USD")
    p.add_argument("--cycle", type=int, default=60, help="seconds between cycles")
    p.add_argument("--port", type=int, default=8901, help="dashboard port")
    p.add_argument("--db", type=Path, default=None,
                   help="ledger path (default ledger.db); separate ledgers "
                        "are separate bodies, but every body shares the soul")
    args = p.parse_args()
    if args.stake <= 0:
        p.error("--stake must be positive; a $0 life is not a life")

    agent = Agent(stake=args.stake, cycle_seconds=args.cycle) if args.db is None \
        else Agent(stake=args.stake, cycle_seconds=args.cycle, db_path=args.db)
    agent.start_background()
    serve(agent, port=args.port)


if __name__ == "__main__":
    main()
