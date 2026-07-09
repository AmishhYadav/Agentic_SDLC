"""Run metadata storage.

Thin sqlite3 module (sync — this is a small, infrequent read/write, not the hot
checkpoint path) storing a `runs` table in the SAME sqlite file the
AsyncSqliteSaver checkpointer uses (read from CHECKPOINT_DB_PATH), just a
different table. Do not create a second sqlite file for this.
"""

import os
import sqlite3
from datetime import datetime, timezone


def _db_path() -> str:
    return os.environ.get("CHECKPOINT_DB_PATH", "./checkpoints.sqlite")


def init_db() -> None:
    """Create the `runs` table if it does not already exist. Idempotent."""
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                lead_email TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_run_record(run_id: str, lead_email: str) -> None:
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            "INSERT INTO runs (run_id, lead_email, created_at) VALUES (?, ?, ?)",
            (run_id, lead_email, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_run_record(run_id: str) -> dict | None:
    conn = sqlite3.connect(_db_path())
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()
