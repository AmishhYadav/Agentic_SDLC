"""Shared TeamMember Pydantic model.

Team members are typed in manually by the lead (name, email, designation,
skills text, experience level) per CLAUDE.md's non-negotiable constraint —
never pulled from an org directory. Email is required even though TEAM-01's
wording omits it, since Phase 3 assignment + ADO push (System.AssignedTo)
depend on a resolvable email string (D-05).

This is the ONE shared shape for team member data — both the db layer
(team_roster.py) and the FastAPI router import this class directly.
"""

from typing import Literal

from pydantic import BaseModel, EmailStr

# Experience level is a fixed four-value set so the frontend's select input
# matches exactly what the backend accepts. Values: "junior", "mid",
# "senior", "lead".
ExperienceLevel = Literal["junior", "mid", "senior", "lead"]


class TeamMember(BaseModel):
    id: str | None = None  # server-assigned on create; present on read/update
    name: str
    email: EmailStr
    designation: str
    skills: str  # free text (D-06) — never a list/enum; Phase 3 reconciles
    experience_level: ExperienceLevel
