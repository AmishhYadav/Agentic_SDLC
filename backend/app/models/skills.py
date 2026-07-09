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


def validate_skill_tags(plan) -> None:
    """Raise ValueError listing every task whose skill_tag is outside SKILL_TAXONOMY.

    Approach (b) from Pitfall 4 / Task 0's discretion: Task.skill_tag stays
    `str | None` on the shared model (avoiding invasiveness to
    push_to_ado.py/frontend consumers), and taxonomy compliance is enforced
    here as an explicit post-parse validation step called from
    services/llm.py's repair loop — exactly like a schema validation failure.
    """
    violations: list[str] = []
    for epic in plan.epics:
        for task in epic.tasks:
            if task.skill_tag is not None and task.skill_tag not in SKILL_TAXONOMY:
                violations.append(f"task {task.id!r} has skill_tag {task.skill_tag!r}")
    if violations:
        raise ValueError(
            "skill_tag values outside SKILL_TAXONOMY: " + "; ".join(violations)
        )
