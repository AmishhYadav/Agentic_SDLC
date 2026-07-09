"""GET/POST/PUT/DELETE /team routes — team roster CRUD (TEAM-01/TEAM-02).

Independent of the LangGraph run — never touches app.graph.* or RunState
(per research's Architectural Responsibility Map). Thin routes calling
straight into app.db.team_roster.
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.db import team_roster
from app.models.team import TeamMember

router = APIRouter()


@router.get("/team")
def list_team() -> list[TeamMember]:
    return team_roster.list_members()


@router.post("/team", status_code=201)
def create_team_member(member: TeamMember) -> TeamMember:
    return team_roster.create_member(member)


@router.put("/team/{member_id}")
def update_team_member(member_id: str, member: TeamMember):
    try:
        return team_roster.update_member(member_id, member)
    except ValueError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc)})


@router.delete("/team/{member_id}", status_code=204)
def delete_team_member(member_id: str):
    team_roster.delete_member(member_id)
    return Response(status_code=204)
