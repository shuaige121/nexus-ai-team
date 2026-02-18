"""SQLite database for token logs, activation records, and analytics."""

import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DASHBOARD_DB_PATH", "dashboard/backend/dashboard.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS token_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT '',
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0.0,
                contract_id TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS activation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                contract_id TEXT DEFAULT NULL,
                choice TEXT DEFAULT NULL,
                token_used INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL DEFAULT 'task',
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'pending',
                objective TEXT DEFAULT '',
                payload TEXT DEFAULT '{}',
                parent_id TEXT DEFAULT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_token_logs_agent ON token_logs(agent_name);
            CREATE INDEX IF NOT EXISTS idx_token_logs_created ON token_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_activation_logs_agent ON activation_logs(agent_name);
            CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
        """)


def log_tokens(agent_name: str, model: str, provider: str,
               prompt_tokens: int, completion_tokens: int,
               cost_usd: float, contract_id: str | None = None):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO token_logs
               (agent_name, model, provider, prompt_tokens, completion_tokens,
                total_tokens, cost_usd, contract_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent_name, model, provider, prompt_tokens, completion_tokens,
             prompt_tokens + completion_tokens, cost_usd, contract_id)
        )


def log_activation(agent_name: str, contract_id: str | None,
                   choice: str | None, token_used: int, status: str = "completed"):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO activation_logs
               (agent_name, contract_id, choice, token_used, status)
               VALUES (?, ?, ?, ?, ?)""",
            (agent_name, contract_id, choice, token_used, status)
        )


def get_token_stats(range_days: int = 7, agent_name: str | None = None):
    with get_db() as conn:
        where = "WHERE created_at >= datetime('now', ?)"
        params: list = [f"-{range_days} days"]
        if agent_name:
            where += " AND agent_name = ?"
            params.append(agent_name)

        rows = conn.execute(
            f"""SELECT date(created_at) as day, agent_name,
                       SUM(prompt_tokens) as input_tokens,
                       SUM(completion_tokens) as output_tokens,
                       SUM(total_tokens) as total,
                       SUM(cost_usd) as cost,
                       COUNT(*) as calls
                FROM token_logs {where}
                GROUP BY day, agent_name
                ORDER BY day""",
            params
        ).fetchall()
        return [dict(r) for r in rows]


def get_agent_performance(agent_name: str | None = None):
    with get_db() as conn:
        where = ""
        params: list = []
        if agent_name:
            where = "WHERE agent_name = ?"
            params = [agent_name]

        rows = conn.execute(
            f"""SELECT agent_name,
                       COUNT(*) as total_tasks,
                       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status='rework' THEN 1 ELSE 0 END) as reworked,
                       AVG(token_used) as avg_tokens
                FROM activation_logs {where}
                GROUP BY agent_name""",
            params
        ).fetchall()
        return [dict(r) for r in rows]
