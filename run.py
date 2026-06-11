#!/usr/bin/env python3
"""Monetize Compute. Stake it, start it, watch it earn or die.

    python3 run.py [--stake 5.0] [--cycle 60] [--port 8901]
"""

import argparse

from mc.loop import Agent
from mc.server import serve


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stake", type=float, default=5.0, help="starting wallet, USD")
    p.add_argument("--cycle", type=int, default=60, help="seconds between cycles")
    p.add_argument("--port", type=int, default=8901, help="dashboard port")
    args = p.parse_args()
    if args.stake <= 0:
        p.error("--stake must be positive; a $0 life is not a life")

    agent = Agent(stake=args.stake, cycle_seconds=args.cycle)
    agent.start_background()
    serve(agent, port=args.port)


if __name__ == "__main__":
    main()
