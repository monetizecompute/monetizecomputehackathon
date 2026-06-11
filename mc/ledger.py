"""The ledger is the agent's metabolism. Every token in, every dollar out.

SQLite, append-only. Three kinds of entries:
  debit   - inference spend, priced per token at Nebius rates
  banked  - confirmed cash in (a paid bounty, a tip, a sale)
  booked  - committed-but-unpaid revenue (a submitted bounty PR awaiting payout)

Balance = starting stake + banked - debits. Booked is reported separately and
never spendable. The agent can only think against money it actually has.
"""

import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "ledger.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('debit', 'banked', 'booked')),
    amount_usd REAL NOT NULL,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    model TEXT,
    memo TEXT,
    proof_url TEXT
);
"""


class Ledger:
    def __init__(self, db_path: Path = DB_PATH, starting_stake: float = 5.0):
        self.starting_stake = starting_stake
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def _add(self, kind, amount, tokens_in=0, tokens_out=0, model=None, memo=None, proof_url=None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO entries (ts, kind, amount_usd, tokens_in, tokens_out, model, memo, proof_url)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), kind, amount, tokens_in, tokens_out, model, memo, proof_url),
            )
            self._conn.commit()

    def debit(self, amount_usd, tokens_in, tokens_out, model, memo):
        self._add("debit", amount_usd, tokens_in, tokens_out, model, memo)

    def bank(self, amount_usd, memo, proof_url=None):
        self._add("banked", amount_usd, memo=memo, proof_url=proof_url)

    def book(self, amount_usd, memo, proof_url=None):
        self._add("booked", amount_usd, memo=memo, proof_url=proof_url)

    def _sum(self, kind):
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) FROM entries WHERE kind = ?", (kind,)
        ).fetchone()
        return row[0]

    def balance(self):
        return self.starting_stake + self._sum("banked") - self._sum("debit")

    def stats(self):
        spent = self._sum("debit")
        banked = self._sum("banked")
        booked = self._sum("booked")
        row = self._conn.execute(
            "SELECT COALESCE(SUM(tokens_in + tokens_out), 0), COUNT(*) FROM entries WHERE kind = 'debit'"
        ).fetchone()
        tokens, calls = row
        return {
            "starting_stake": self.starting_stake,
            "balance": self.starting_stake + banked - spent,
            "spent": spent,
            "banked": banked,
            "booked": booked,
            "net": banked - spent,
            "tokens": tokens,
            "calls": calls,
            # The headline metric: dollars earned per million tokens burned.
            "rev_per_mtok": (banked / tokens * 1_000_000) if tokens else 0.0,
        }

    def recent(self, limit=50):
        rows = self._conn.execute(
            "SELECT ts, kind, amount_usd, tokens_in, tokens_out, model, memo, proof_url"
            " FROM entries ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        keys = ["ts", "kind", "amount_usd", "tokens_in", "tokens_out", "model", "memo", "proof_url"]
        return [dict(zip(keys, r)) for r in rows]
