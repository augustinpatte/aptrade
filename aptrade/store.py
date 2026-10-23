"""SQLite journal: every run with its full parameters, and every trade it produced.
One file, queryable, so you can compare runs instead of trusting your memory."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TRADE_COLUMNS = [
    "symbol", "day", "side", "entry_bar", "exit_bar", "signal_time", "ref_price", "fill", "stop",
    "target", "exit", "exit_reason", "exit_time", "risk_ps", "risk_pct", "r_gross", "r_net",
    "taken", "qty", "pnl", "reject",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    kind        TEXT NOT NULL,           -- backtest | sweep | holdout
    strategy    TEXT NOT NULL,
    params      TEXT NOT NULL,           -- JSON
    exec        TEXT NOT NULL,           -- JSON
    universe    TEXT NOT NULL,           -- JSON list
    start       TEXT NOT NULL,
    end         TEXT NOT NULL,
    feed        TEXT NOT NULL,
    summary     TEXT NOT NULL            -- JSON
);
CREATE TABLE IF NOT EXISTS trades (
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    symbol TEXT, day TEXT, side TEXT, entry_bar INTEGER, exit_bar INTEGER, signal_time TEXT,
    ref_price REAL, fill REAL, stop REAL, target REAL,
    exit REAL, exit_reason TEXT, exit_time TEXT,
    risk_ps REAL, risk_pct REAL, r_gross REAL, r_net REAL,
    taken INTEGER, qty INTEGER, pnl REAL, reject TEXT   -- portfolio simulation, NULL if not run
);
CREATE INDEX IF NOT EXISTS trades_run ON trades(run_id);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (           -- live/paper rebalancing plans and what happened to them
    id          TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    mode        TEXT NOT NULL,               -- paper | live
    status      TEXT NOT NULL,               -- planned | executed | partial | refused | error
    plan        TEXT NOT NULL,               -- JSON
    result      TEXT                         -- JSON
);
CREATE TABLE IF NOT EXISTS equity (          -- daily account value, for brokers without a history API
    day    TEXT NOT NULL,
    broker TEXT NOT NULL,
    mode   TEXT NOT NULL,
    equity REAL NOT NULL,
    PRIMARY KEY (day, broker, mode)
);
"""


def _json(x) -> str:
    return json.dumps(x, default=str, sort_keys=True)


@contextmanager
def connect(path: Path):
    """A connection that commits on success, rolls back on error, and always closes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def save_run(path: Path, *, kind, strategy, params, exec_cfg, universe, start, end, feed,
             summary, trades: pd.DataFrame) -> int:
    with connect(path) as con:
        cur = con.execute(
            "INSERT INTO runs (created_utc, kind, strategy, params, exec, universe, start, end, feed, summary)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, strategy, _json(params),
             _json(exec_cfg), _json(list(universe)), str(start), str(end), feed, _json(summary)))
        run_id = cur.lastrowid
        if not trades.empty:
            t = trades.reindex(columns=TRADE_COLUMNS).copy()
            t["day"] = t["day"].astype(str)
            t.insert(0, "run_id", run_id)
            t.to_sql("trades", con, if_exists="append", index=False)
    return run_id


def load_run(path: Path, run_id: int) -> tuple[dict, pd.DataFrame]:
    with connect(path) as con:
        row = con.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no run {run_id}")
        cols = [d[0] for d in con.execute("SELECT * FROM runs LIMIT 0").description]
        run = dict(zip(cols, row))
        for k in ("params", "exec", "universe", "summary"):
            run[k] = json.loads(run[k])
        trades = pd.read_sql_query("SELECT * FROM trades WHERE run_id = ?", con, params=(run_id,))
    return run, trades


def list_runs(path: Path, limit: int = 20) -> pd.DataFrame:
    with connect(path) as con:
        df = pd.read_sql_query(
            "SELECT id, created_utc, kind, strategy, params, start, end, feed, summary "
            "FROM runs ORDER BY id DESC LIMIT ?", con, params=(limit,))
    if df.empty:
        return df
    s = df.pop("summary").map(json.loads)
    df["trades"] = s.map(lambda x: x.get("trades"))
    df["avg_r_net"] = s.map(lambda x: round(x["avg_r_net"], 3) if "avg_r_net" in x else None)
    return df


# ------------------------------------------------------------------ holdout

def get_meta(path: Path, key: str) -> str | None:
    with connect(path) as con:
        row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(path: Path, key: str, value: str) -> None:
    with connect(path) as con:
        con.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def holdout_views(path: Path, kind: str = "holdout", strategy: str | None = None) -> int:
    """How many times this holdout was looked at (for one strategy, if given)."""
    with connect(path) as con:
        if strategy is None:
            return con.execute("SELECT COUNT(*) FROM runs WHERE kind = ?", (kind,)).fetchone()[0]
        return con.execute("SELECT COUNT(*) FROM runs WHERE kind = ? AND strategy = ?",
                           (kind, strategy)).fetchone()[0]


# ------------------------------------------------------------------ live plans

def save_plan(path: Path, plan: dict) -> None:
    with connect(path) as con:
        con.execute("INSERT INTO plans (id, created_utc, mode, status, plan) VALUES (?,?,?,?,?)",
                    (plan["id"], plan["created_utc"], plan["mode"], "planned", _json(plan)))


def get_plan(path: Path, plan_id: str) -> tuple[dict, str] | None:
    with connect(path) as con:
        row = con.execute("SELECT plan, status FROM plans WHERE id = ?", (plan_id,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else None


def set_plan_result(path: Path, plan_id: str, status: str, result: dict) -> None:
    with connect(path) as con:
        con.execute("UPDATE plans SET status = ?, result = ? WHERE id = ?", (status, _json(result), plan_id))


def executed_today(path: Path, mode: str) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    with connect(path) as con:
        return con.execute("SELECT COUNT(*) FROM plans WHERE mode = ? AND status IN ('executed', 'partial') "
                           "AND substr(created_utc, 1, 10) = ?", (mode, today)).fetchone()[0]


def last_executed(path: Path, mode: str) -> str | None:
    with connect(path) as con:
        row = con.execute("SELECT max(created_utc) FROM plans WHERE mode = ? AND status IN ('executed', 'partial')",
                          (mode,)).fetchone()
    return row[0] if row else None


def record_equity(path: Path, broker: str, mode: str, equity: float) -> None:
    day = datetime.now(timezone.utc).date().isoformat()
    with connect(path) as con:
        con.execute("INSERT OR REPLACE INTO equity (day, broker, mode, equity) VALUES (?, ?, ?, ?)",
                    (day, broker, mode, float(equity)))


def equity_history(path: Path, broker: str, mode: str, days: int = 366) -> list[float]:
    with connect(path) as con:
        rows = con.execute("SELECT equity FROM equity WHERE broker = ? AND mode = ? ORDER BY day DESC LIMIT ?",
                           (broker, mode, days)).fetchall()
    return [r[0] for r in reversed(rows)]
