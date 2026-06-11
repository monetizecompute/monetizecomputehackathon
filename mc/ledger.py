"""The ledger is the agent's metabolism. Every token in, every dollar out.

SQLite, append-only. Three kinds of entries:
  debit   - inference spend, priced per token at Nebius rates
  banked  - confirmed cash in (a paid bounty, a tip, a sale)
  booked  - committed-but-unpaid revenue (a submitted bounty PR awaiting payout)

Balance = stake + banked - debits - the last-words reserve. The reserve is a
few cents escrowed outside spendable balance so a dying agent can afford its
own epitaph. The agent can only think against money it actually has.

Lives are generations. Each life gets the same stake and dies alone, but its
will carries forward. Money does not survive death. Knowledge does.
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
    gen INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL CHECK (kind IN ('debit', 'banked', 'booked')),
    amount_usd REAL NOT NULL,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    model TEXT,
    memo TEXT,
    proof_url TEXT,
    source TEXT NOT NULL DEFAULT 'earned'
        CHECK (source IN ('earned', 'donation'))
);
CREATE TABLE IF NOT EXISTS lives (
    gen INTEGER PRIMARY KEY,
    born_ts REAL NOT NULL,
    died_ts REAL,
    cause TEXT,
    epitaph TEXT,
    will TEXT
);
"""


class Ledger:
    def __init__(self, db_path: Path = DB_PATH, starting_stake: float = 5.0,
                 reserve: float = 0.05):
        self.starting_stake = starting_stake
        # Last-words escrow can never exceed a tenth of the stake; a tiny
        # stake should buy a short life, not a stillbirth.
        self.reserve = min(reserve, starting_stake / 10)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        cols = [r[1] for r in self._conn.execute("PRAGMA table_info(entries)")]
        if "source" not in cols:  # ledgers created before the earned/donation split
            self._conn.execute(
                "ALTER TABLE entries ADD COLUMN source TEXT NOT NULL DEFAULT 'earned'")
        self._conn.commit()
        self.gen = self._resume_or_start_life()

    # -- lives ------------------------------------------------------------

    def _resume_or_start_life(self):
        """Resume a life in progress, or report a death. A restart never
        mints a new generation: that would be a free resurrection, and
        revenue is the only revival."""
        self.born_dead = False
        row = self._conn.execute(
            "SELECT gen, died_ts FROM lives ORDER BY gen DESC LIMIT 1"
        ).fetchone()
        if row and row[1] is None:
            return row[0]  # a life in progress; pick it back up
        if row:
            self.born_dead = True  # dead is dead until money arrives
            return row[0]
        self._conn.execute(
            "INSERT INTO lives (gen, born_ts) VALUES (?, ?)", (1, time.time()))
        self._conn.commit()
        return 1

    def begin_next_life(self):
        with self._lock:
            self.gen += 1
            self._conn.execute(
                "INSERT INTO lives (gen, born_ts) VALUES (?, ?)",
                (self.gen, time.time()))
            self._conn.commit()
        return self.gen

    def end_life(self, cause, epitaph=None, will=None):
        with self._lock:
            self._conn.execute(
                "UPDATE lives SET died_ts = ?, cause = ?, epitaph = ?, will = ?"
                " WHERE gen = ?",
                (time.time(), cause, epitaph, will, self.gen))
            self._conn.commit()

    def wills(self, limit=3):
        with self._lock:
            rows = self._conn.execute(
                "SELECT gen, will FROM lives WHERE will IS NOT NULL"
                " ORDER BY gen DESC LIMIT ?", (limit,)).fetchall()
        return [{"gen": g, "will": w} for g, w in rows][::-1]

    def lives(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT l.gen, l.born_ts, l.died_ts, l.cause, l.epitaph,"
                " COALESCE(SUM(CASE WHEN e.kind = 'debit'"
                "   THEN e.tokens_in + e.tokens_out END), 0),"
                " COALESCE(SUM(CASE WHEN e.kind = 'banked' THEN e.amount_usd END), 0)"
                " - COALESCE(SUM(CASE WHEN e.kind = 'debit' THEN e.amount_usd END), 0)"
                " FROM lives l LEFT JOIN entries e ON e.gen = l.gen"
                " GROUP BY l.gen ORDER BY l.gen DESC").fetchall()
        keys = ["gen", "born_ts", "died_ts", "cause", "epitaph", "tokens", "net"]
        return [dict(zip(keys, r)) for r in rows]

    # -- money ------------------------------------------------------------

    def _add(self, kind, amount, tokens_in=0, tokens_out=0, model=None,
             memo=None, proof_url=None, source="earned"):
        with self._lock:
            self._conn.execute(
                "INSERT INTO entries (ts, gen, kind, amount_usd, tokens_in,"
                " tokens_out, model, memo, proof_url, source)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), self.gen, kind, amount, tokens_in, tokens_out,
                 model, memo, proof_url, source))
            self._conn.commit()

    def debit(self, amount_usd, tokens_in, tokens_out, model, memo):
        self._add("debit", amount_usd, tokens_in, tokens_out, model, memo)

    def bank(self, amount_usd, memo, proof_url=None, source="earned"):
        """Donations spend the same as earnings but never count as revenue
        the agent generated. The headline metric only sees earned money.
        Unknown sources coerce to the unflattering side."""
        self._add("banked", amount_usd, memo=memo, proof_url=proof_url,
                  source=source if source in ("earned", "donation") else "donation")

    def book(self, amount_usd, memo, proof_url=None):
        self._add("booked", amount_usd, memo=memo, proof_url=proof_url)

    def _sum(self, kind):
        # Caller must hold self._lock.
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) FROM entries"
            " WHERE kind = ? AND gen = ?", (kind, self.gen)).fetchone()
        return row[0]

    def balance(self):
        """Spendable money this life: stake plus earnings, minus spend, minus
        the escrowed last-words reserve."""
        with self._lock:
            return (self.starting_stake - self.reserve
                    + self._sum("banked") - self._sum("debit"))

    def stats(self):
        # One lock acquisition for the whole snapshot, so the dashboard never
        # sees a balance and a spend that disagree about the same moment.
        with self._lock:
            spent = self._sum("debit")
            banked = self._sum("banked")
            booked = self._sum("booked")
            earned = self._conn.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) FROM entries"
                " WHERE kind = 'banked' AND source = 'earned' AND gen = ?",
                (self.gen,)).fetchone()[0]
            row = self._conn.execute(
                "SELECT COALESCE(SUM(tokens_in + tokens_out), 0), COUNT(*)"
                " FROM entries WHERE kind = 'debit' AND gen = ?",
                (self.gen,)).fetchone()
        tokens, calls = row
        return {
            "gen": self.gen,
            "starting_stake": self.starting_stake,
            "reserve": self.reserve,
            "balance": self.starting_stake - self.reserve + banked - spent,
            "spent": spent,
            "banked": banked,
            "earned": earned,
            "donated": banked - earned,
            "booked": booked,
            "net": banked - spent,
            "tokens": tokens,
            "calls": calls,
            # The headline metric: dollars EARNED per million tokens burned.
            # Donations keep the agent alive; they do not flatter this number.
            "rev_per_mtok": (earned / tokens * 1_000_000) if tokens else 0.0,
        }

    def recent(self, limit=50):
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, gen, kind, amount_usd, tokens_in, tokens_out, model,"
                " memo, proof_url FROM entries ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
        keys = ["ts", "gen", "kind", "amount_usd", "tokens_in", "tokens_out",
                "model", "memo", "proof_url"]
        return [dict(zip(keys, r)) for r in rows]
