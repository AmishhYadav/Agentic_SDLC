"""Deterministic, skill-aware, load-balanced task assignment.

Never called by the LLM (D-14: suggested_assignee starts blank out of
generate_plan and is filled in here, in plain Python) — this module is the
one place `suggested_assignee` gets a real value before human review.
"""

from app.models.plan import Plan
from app.models.team import TeamMember
from app.services.skill_match import skill_covered_by

_EXPERIENCE_SCORE: dict[str, float] = {
    "junior": 0.5,
    "mid": 1.0,
    "senior": 1.5,
    "lead": 2.0,
}


def _score(task_skill_tag: str, member: TeamMember, load: dict[str, float]) -> float:
    skill_score = 1 if skill_covered_by(task_skill_tag, member.skills) else 0
    exp_score = _EXPERIENCE_SCORE[member.experience_level]
    current_load = load.get(member.email, 0.0)
    return skill_score * 10 + exp_score - current_load * 0.1


def assign_plan(plan: Plan, team: list[TeamMember]) -> Plan:
    """Return a NEW Plan with every task's suggested_assignee resolved.

    Never mutates the input plan. If team is empty, every suggested_assignee
    is set to "". Otherwise iterates tasks in plan order, maintaining a
    running per-member hour load so assignment naturally balances across the
    team as tasks accumulate. Deterministic: ties broken by lowest current
    load, then member name.
    """
    new_plan = plan.model_copy(deep=True)

    if not team:
        for epic in new_plan.epics:
            for task in epic.tasks:
                task.suggested_assignee = ""
        return new_plan

    load: dict[str, float] = {member.email: 0.0 for member in team}

    for epic in new_plan.epics:
        for task in epic.tasks:
            skill_tag = task.skill_tag or ""
            best_member = min(
                team,
                key=lambda m: (
                    -_score(skill_tag, m, load),
                    load.get(m.email, 0.0),
                    m.name,
                ),
            )
            task.suggested_assignee = best_member.email
            load[best_member.email] = load.get(best_member.email, 0.0) + task.estimate_hours

    return new_plan
