"""Coverage for TEAM-01/TEAM-02: team_members SQLite CRUD (backend/app/db/team_roster.py),
the TeamMember Pydantic model's email validation, and the /team FastAPI CRUD routes.

Uses a per-test temp sqlite file via the CHECKPOINT_DB_PATH env var (monkeypatch),
mirroring the mock_ado_env style already used in this suite — no shared on-disk
state between tests.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.db import team_roster
from app.models.team import TeamMember


@pytest.fixture
def team_db(tmp_path, monkeypatch):
    """Point CHECKPOINT_DB_PATH at a fresh temp sqlite file and init the table."""
    db_path = tmp_path / "test_checkpoints.sqlite"
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(db_path))
    team_roster.init_team_table()
    return db_path


@pytest.fixture
def app_client(team_db):
    """A minimal FastAPI app with just the team router mounted, for route tests."""
    from app.routers.team import router as team_router

    app = FastAPI()
    app.include_router(team_router)
    return TestClient(app)


def _sample_member(**overrides) -> TeamMember:
    fields = dict(
        name="Ada Lovelace",
        email="ada@example.com",
        designation="Senior Engineer",
        skills="Python, distributed systems",
        experience_level="senior",
    )
    fields.update(overrides)
    return TeamMember(**fields)


# --- Test 1: create_member + list_members ---


def test_create_member_inserts_and_list_includes_it(team_db):
    created = team_roster.create_member(_sample_member())

    assert created.id is not None
    members = team_roster.list_members()
    assert len(members) == 1
    assert members[0].id == created.id
    assert members[0].name == "Ada Lovelace"
    assert members[0].email == "ada@example.com"
    assert members[0].designation == "Senior Engineer"
    assert members[0].skills == "Python, distributed systems"
    assert members[0].experience_level == "senior"


# --- Test 2: update_member ---


def test_update_member_changes_fields_and_reflects_in_list(team_db):
    created = team_roster.create_member(_sample_member())

    updated = team_roster.update_member(
        created.id,
        _sample_member(designation="Staff Engineer", skills="Rust, Kubernetes"),
    )

    assert updated.designation == "Staff Engineer"
    assert updated.skills == "Rust, Kubernetes"

    members = team_roster.list_members()
    assert len(members) == 1
    assert members[0].designation == "Staff Engineer"
    assert members[0].skills == "Rust, Kubernetes"


def test_update_member_nonexistent_id_raises_value_error(team_db):
    with pytest.raises(ValueError):
        team_roster.update_member("does-not-exist", _sample_member())


# --- Test 3: delete_member ---


def test_delete_member_removes_row(team_db):
    created = team_roster.create_member(_sample_member())

    team_roster.delete_member(created.id)

    members = team_roster.list_members()
    assert members == []


def test_delete_member_nonexistent_id_is_idempotent(team_db):
    # Should not raise.
    team_roster.delete_member("does-not-exist")


# --- Test 4: TeamMember email validation ---


def test_team_member_rejects_invalid_email():
    with pytest.raises(ValidationError):
        TeamMember(
            name="Bad Email",
            email="not-an-email",
            designation="Engineer",
            skills="Python",
            experience_level="mid",
        )


def test_team_member_accepts_valid_email():
    member = _sample_member()
    assert member.email == "ada@example.com"


# --- Test 5: full CRUD round-trip via FastAPI TestClient ---


def test_team_crud_round_trip_via_http(app_client):
    create_body = {
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "designation": "Principal Engineer",
        "skills": "COBOL, compilers",
        "experience_level": "lead",
    }
    create_resp = app_client.post("/team", json=create_body)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["id"] is not None
    assert created["name"] == "Grace Hopper"

    list_resp = app_client.get("/team")
    assert list_resp.status_code == 200
    members = list_resp.json()
    assert len(members) == 1
    assert members[0]["id"] == created["id"]

    update_body = dict(create_body)
    update_body["designation"] = "Distinguished Engineer"
    update_resp = app_client.put(f"/team/{created['id']}", json=update_body)
    assert update_resp.status_code == 200
    assert update_resp.json()["designation"] == "Distinguished Engineer"

    delete_resp = app_client.delete(f"/team/{created['id']}")
    assert delete_resp.status_code == 204

    final_list_resp = app_client.get("/team")
    assert final_list_resp.status_code == 200
    assert final_list_resp.json() == []


def test_team_update_nonexistent_returns_404(app_client):
    body = {
        "name": "Ghost",
        "email": "ghost@example.com",
        "designation": "N/A",
        "skills": "N/A",
        "experience_level": "junior",
    }
    resp = app_client.put("/team/does-not-exist", json=body)
    assert resp.status_code == 404
