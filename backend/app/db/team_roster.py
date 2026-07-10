"""Team roster storage.

Thin sqlite3 module (sync, mirroring run_metadata.py's style exactly) storing
a `team_members` table in the SAME sqlite file the AsyncSqliteSaver
checkpointer and run_metadata.py use (read from CHECKPOINT_DB_PATH), just a
different table. Do not create a second sqlite file for this.

Per D-04, the roster is global and persisted as a single current set reused
across runs — never a per-run snapshot, never part of RunState. This module
must never import from app.graph.* (see 02-02-PLAN.md success_criteria).
"""

import os
import sqlite3
import uuid

from app.models.team import TeamMember


def _db_path() -> str:
    return os.environ.get("CHECKPOINT_DB_PATH", "./checkpoints.sqlite")


def init_team_table() -> None:
    """Create the `team_members` table if it does not already exist. Idempotent."""
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                designation TEXT,
                skills TEXT,
                experience_level TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_member(member: TeamMember) -> TeamMember:
    member_id = uuid.uuid4().hex
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute(
            """
            INSERT INTO team_members (id, name, email, designation, skills, experience_level)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                member_id,
                member.name,
                member.email,
                member.designation,
                member.skills,
                member.experience_level,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return member.model_copy(update={"id": member_id})


def list_members() -> list[TeamMember]:
    conn = sqlite3.connect(_db_path())
    try:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                designation TEXT,
                skills TEXT,
                experience_level TEXT
            )
            """
        )
        cur = conn.execute(
            "SELECT id, name, email, designation, skills, experience_level FROM team_members"
        )
        rows = cur.fetchall()
        return [TeamMember(**dict(row)) for row in rows]
    finally:
        conn.close()


def update_member(member_id: str, member: TeamMember) -> TeamMember:
    conn = sqlite3.connect(_db_path())
    try:
        cur = conn.execute(
            """
            UPDATE team_members
            SET name = ?, email = ?, designation = ?, skills = ?, experience_level = ?
            WHERE id = ?
            """,
            (
                member.name,
                member.email,
                member.designation,
                member.skills,
                member.experience_level,
                member_id,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise ValueError(f"team member {member_id} not found")
    finally:
        conn.close()
    return member.model_copy(update={"id": member_id})


def delete_member(member_id: str) -> None:
    conn = sqlite3.connect(_db_path())
    try:
        conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
        conn.commit()
    finally:
        conn.close()
