"""Fixed skill taxonomy (D-10, PLAN-02).

Single canonical constant for the task-skill taxonomy. Importable by both the
plan-generation node/service and any future Phase 3 API/model consumers that
reconcile team-member free-text skills (D-06) against this same list — do not
duplicate this list anywhere else.
"""

SKILL_TAXONOMY: list[str] = [
    "Frontend",
    "Backend",
    "Database",
    "DevOps",
    "Testing",
    "API-Design",
    "Auth",
    "Infra",
    "Mobile",
    "Data-Engineering",
    "ML",
    "Security",
    "Documentation",
    "UX-Design",
    "Integration",
]


def validate_skill_tags(plan, skill_taxonomy: list[str] | None = None) -> None:
    """Raise ValueError listing every task whose skill_tag is outside the taxonomy.

    Approach (b) from Pitfall 4 / Task 0's discretion: Task.skill_tag stays
    `str | None` on the shared model (avoiding invasiveness to
    push_to_ado.py/frontend consumers), and taxonomy compliance is enforced
    here as an explicit post-parse validation step called from
    services/llm.py's repair loop — exactly like a schema validation failure.

    skill_taxonomy defaults to the canonical SKILL_TAXONOMY constant; callers
    may pass an explicit list (e.g. services/llm.py threads the same list it
    used to build the prompt) so the taxonomy checked against is always the
    one the LLM was actually instructed to use.
    """
    taxonomy = skill_taxonomy if skill_taxonomy is not None else SKILL_TAXONOMY
    violations: list[str] = []
    for epic in plan.epics:
        for task in epic.tasks:
            if task.skill_tag is not None and task.skill_tag not in taxonomy:
                violations.append(f"task {task.id!r} has skill_tag {task.skill_tag!r}")
    if violations:
        raise ValueError(
            "skill_tag values outside taxonomy: " + "; ".join(violations)
        )
