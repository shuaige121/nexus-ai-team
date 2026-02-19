"""Checkpoint persistence for NEXUS orchestrator.

Provides persistent checkpointing for LangGraph state.
Prefers PostgresSaver when NEXUS_PG_URL is set; falls back to SqliteSaver
(file-based, ~/.nexus/checkpoints.db).
"""
from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

# Module-level singleton to avoid creating multiple connections/savers
_checkpointer = None


def get_checkpointer():
    """Get the appropriate checkpointer based on available backends.

    Priority:
        1. PostgresSaver -- if NEXUS_PG_URL env var is set
        2. SqliteSaver   -- file-based fallback (always available)

    The saver instance is cached as a module-level singleton so that
    repeated calls (e.g. per-request in FastAPI) reuse the same
    connection and checkpoint store.

    Returns:
        A LangGraph BaseCheckpointSaver instance.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    pg_url = os.getenv("NEXUS_PG_URL")
    if pg_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            saver = PostgresSaver.from_conn_string(pg_url)
            logger.info("[CHECKPOINT] Using PostgresSaver (url=%s...)", pg_url[:25])
            _checkpointer = saver
            return saver
        except Exception:
            logger.warning(
                "[CHECKPOINT] PostgresSaver failed, falling back to SQLite",
                exc_info=True,
            )

    # Fallback: SQLite file-based persistence
    db_path = os.path.expanduser("~/.nexus/checkpoints.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    logger.info("[CHECKPOINT] Using SqliteSaver (path=%s)", db_path)
    _checkpointer = saver
    return saver
