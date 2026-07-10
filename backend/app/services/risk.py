"""Deterministic risk scoring — PURE PYTHON, never the LLM.

CLAUDE.md's non-negotiable constraint: "Risk score must be computed in plain
Python, never by the LLM. The LLM may only generate the narrative explanation
that sits next to the number." This module computes score/level/items purely
from the Plan + team roster; narrate_risk_offline builds a deterministic
offline template string, never a real LLM call.
"""

from app.models.plan import Plan
from app.models.risk import RiskItem, RiskReport
from app.models.team import TeamMember
from app.services.skill_match import skill_covered_by

_NARRATIVE_PREFIX = "AI-suggested risk summary (verify before relying): "


def _severity_for_share(share: float) -> str:
    if share < 0.15:
        return "low"
    if share < 0.3:
        return "medium"
    return "high"


def _level_for_score(score: int) -> str:
    if score < 20:
        return "low"
    if score < 50:
        return "medium"
    return "high"


def narrate_risk_offline(report: RiskReport) -> str:
    """Build a deterministic, offline narrative string for a RiskReport.

    No LLM call — a fixed template summarizing score/level and listing
    uncovered skills (if any).
    """
    if not report.items:
        return (
            f"{_NARRATIVE_PREFIX}score {report.score}/100 ({report.level} risk). "
            "Skill coverage looks complete — every required skill is covered "
            "by at least one team member."
        )

    skill_list = ", ".join(
        f"{item.skill} ({item.hours_at_risk}h, {item.severity})" for item in report.items
    )
    return (
        f"{_NARRATIVE_PREFIX}score {report.score}/100 ({report.level} risk). "
        f"Uncovered skills at risk: {skill_list}."
    )


def compute_risk(plan: Plan, team: list[TeamMember]) -> RiskReport:
    """Compute a RiskReport for plan given team, deterministically.

    - Gathers required skills (non-empty task.skill_tag) and sums
      estimate_hours per skill.
    - A skill is "covered" if any team member's skills text covers it.
    - No team at all -> score=100, level="high", single "(no team)" item.
    - Otherwise score = round(100 * uncovered_hours / total_hours).
    """
    hours_for_skill: dict[str, float] = {}
    total_hours = 0.0
    for epic in plan.epics:
        for task in epic.tasks:
            total_hours += task.estimate_hours
            if task.skill_tag:
                hours_for_skill[task.skill_tag] = (
                    hours_for_skill.get(task.skill_tag, 0.0) + task.estimate_hours
                )

    if not team:
        report = RiskReport(
            score=100,
            level="high",
            items=[
                RiskItem(
                    skill="(no team)",
                    hours_at_risk=total_hours,
                    severity="high",
                    detail="No team members configured — every task is unassigned/at risk.",
                )
            ],
            narrative="",
        )
        report.narrative = narrate_risk_offline(report)
        return report

    uncovered_hours = 0.0
    items: list[RiskItem] = []
    for skill, hours in hours_for_skill.items():
        covered = any(skill_covered_by(skill, member.skills) for member in team)
        if covered:
            continue
        uncovered_hours += hours
        share = (hours / total_hours) if total_hours > 0 else 0.0
        items.append(
            RiskItem(
                skill=skill,
                hours_at_risk=hours,
                severity=_severity_for_share(share),
                detail=f"No team member covers '{skill}' ({hours}h of work at risk).",
            )
        )

    score = round(100 * uncovered_hours / total_hours) if total_hours > 0 else 0
    level = _level_for_score(score)

    # Deterministic ordering for repeatability.
    items.sort(key=lambda item: item.skill)

    report = RiskReport(score=score, level=level, items=items, narrative="")
    report.narrative = narrate_risk_offline(report)
    return report
