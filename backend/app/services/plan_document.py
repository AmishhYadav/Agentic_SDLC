"""Professional plan-document composition (markdown).

Produces the detailed, human-readable implementation plan document that sits
next to the structured Plan JSON in the UI. The structured Plan remains the
single source of truth (CLAUDE.md); this document is a *rendered narrative view*
of it — analogous to the risk narrative and onboarding summary — never a second
structural representation.

Two paths, mirroring generate_plan's LLM-with-offline-fallback pattern:
- If an LLM is available, expand the deterministic fact render into professional
  prose via a fixed prompt template (see llm.build_plan_document_prompt). The
  model is given the finalized plan + Python-computed risk as ground truth and
  is instructed to narrate, never alter, them.
- Otherwise (or on any LLM error), return the deterministic render itself, which
  is guaranteed consistent with the plan JSON and needs no network/API key.

A leading disclaimer is always prepended by the app so the downloadable .md
never leaves the tool implying the estimates/assignees are verified fact.
"""

from app.models.plan import Plan
from app.models.risk import RiskReport
from app.models.team import TeamMember
from app.services.llm import (
    build_chat_llm,
    generate_plan_document_text,
    pipeline_llm_enabled,
)

_DISCLAIMER = (
    "> **AI-generated draft — verify before relying on this.** Estimates, "
    "assignments, and the risk narrative are suggestions, not commitments.\n"
)

_HOURS_PER_DAY = 8.0


def _assignee_display(assignee: str, email_to_name: dict[str, str]) -> str:
    if not assignee:
        return "_unassigned_"
    return email_to_name.get(assignee, assignee)


def _plan_totals(plan: Plan) -> tuple[int, int, float]:
    epic_count = len(plan.epics)
    task_count = sum(len(e.tasks) for e in plan.epics)
    total_hours = sum(t.estimate_hours for e in plan.epics for t in e.tasks)
    return epic_count, task_count, total_hours


def render_plan_document_markdown(
    plan: Plan, risk: RiskReport | None, team: list[TeamMember]
) -> str:
    """Deterministic markdown render of the finalized plan + risk.

    Serves both as the offline fallback document AND as the authoritative
    "facts" block handed to the LLM, so the narrative can never drift from the
    real numbers.
    """
    email_to_name = {m.email: m.name for m in team if m.email}
    epic_count, task_count, total_hours = _plan_totals(plan)
    total_days = total_hours / _HOURS_PER_DAY

    lines: list[str] = []
    lines.append("# Implementation Plan")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- **Epics:** {epic_count}")
    lines.append(f"- **Tasks:** {task_count}")
    lines.append(
        f"- **Total estimated effort:** {total_hours:g} hours "
        f"(~{total_days:.1f} days at {_HOURS_PER_DAY:g}h/day)"
    )
    lines.append(f"- **Team size:** {len(team)}")
    if risk is not None:
        lines.append(
            f"- **Risk:** {risk.level.upper()} ({risk.score}/100)"
        )
    lines.append("")

    if risk is not None:
        lines.append("## Risk Summary")
        lines.append("")
        if risk.narrative:
            lines.append(risk.narrative)
            lines.append("")
        if risk.items:
            for item in risk.items:
                lines.append(
                    f"- **{item.severity.upper()} · {item.skill}** — "
                    f"{item.hours_at_risk:g}h at risk: {item.detail}"
                )
            lines.append("")

    if not plan.epics:
        lines.append("## Epic Breakdown")
        lines.append("")
        lines.append("_No epics were generated for this plan._")
        lines.append("")
    else:
        lines.append("## Epic Breakdown")
        lines.append("")
        for idx, epic in enumerate(plan.epics, start=1):
            lines.append(f"### Epic {idx}: {epic.title}")
            lines.append("")
            if epic.description:
                lines.append(epic.description)
                lines.append("")
            lines.append("| Task | Owner | Skill | Est (h) | Depends on |")
            lines.append("| --- | --- | --- | --- | --- |")
            for task in epic.tasks:
                owner = _assignee_display(task.suggested_assignee, email_to_name)
                skill = task.skill_tag or "—"
                deps = ", ".join(task.depends_on) if task.depends_on else "—"
                lines.append(
                    f"| {task.title} | {owner} | {skill} | "
                    f"{task.estimate_hours:g} | {deps} |"
                )
            epic_hours = sum(t.estimate_hours for t in epic.tasks)
            lines.append("")
            lines.append(f"_Epic subtotal: {epic_hours:g}h_")
            lines.append("")

    lines.append("## Assumptions & Notes")
    lines.append("")
    lines.append(
        "- Estimates and assignments are AI-suggested starting points — "
        "review and adjust them with the team before committing."
    )
    lines.append(
        "- Task dependencies are shown for context only and are not enforced."
    )
    lines.append("")

    return "\n".join(lines)


def render_plan_document_offline(
    plan: Plan, risk: RiskReport | None, team: list[TeamMember]
) -> str:
    """Disclaimer + deterministic render, no LLM. Used to cheaply refresh the
    document after an in-review plan edit so it never drifts from the JSON."""
    return f"{_DISCLAIMER}\n{render_plan_document_markdown(plan, risk, team)}"


def compose_plan_document(
    plan: Plan,
    docs_text: str | None,
    risk: RiskReport | None,
    team: list[TeamMember],
) -> str:
    """Build the plan document, preferring the LLM narrative, falling back to
    the deterministic render. Always prepends the AI-generated disclaimer.

    Fully synchronous (blocking LLM HTTP call) — the graph node runs it off the
    event loop via asyncio.to_thread.
    """
    facts_markdown = render_plan_document_markdown(plan, risk, team)

    body = facts_markdown
    # Only attempt the richer LLM narrative when there's an actual plan to
    # narrate — an empty plan has nothing to expand on.
    if plan.epics and pipeline_llm_enabled():
        try:
            llm = build_chat_llm()
            body = generate_plan_document_text(llm, facts_markdown, docs_text or "")
        except Exception:  # noqa: BLE001 — never let doc generation abort the run
            body = facts_markdown

    return f"{_DISCLAIMER}\n{body}"
