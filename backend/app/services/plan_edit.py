"""Offline natural-language plan editor + unified diff.

Parses a small set of plain-English edit intents (reassign, estimate, split,
remove, rename) against a Plan, entirely offline — no LLM call. Used by the
/runs/{run_id}/edit endpoint to let the lead edit the plan conversationally
before approving it (see project-spec.md's edit_plan loop).
"""

import difflib
import json
import re

from app.models.plan import Epic, Plan, Task
from app.models.team import TeamMember


def _find_task(plan: Plan, taskref: str) -> tuple[Epic, Task] | None:
    """Return (epic, task) for the first task whose title contains taskref (case-insensitive)."""
    needle = taskref.strip().lower()
    if not needle:
        return None
    for epic in plan.epics:
        for task in epic.tasks:
            if needle in task.title.lower():
                return epic, task
    return None


def _find_member(team: list[TeamMember], who: str) -> TeamMember | None:
    """Match `who` against a team member's name (substring) or email (substring), case-insensitive."""
    needle = who.strip().lower()
    if not needle:
        return None
    for member in team:
        if needle in member.name.lower() or needle in member.email.lower():
            return member
    return None


_REASSIGN_RE = re.compile(
    r"(?:re)?assign\s+(?:task\s+)?(?P<taskref>.+?)\s+to\s+(?P<who>.+)$",
    re.IGNORECASE,
)

_ESTIMATE_CHANGE_RE = re.compile(
    r"(?:change|set)\s+.*?estimate.*?\s+(?:for\s+)?(?:task\s+)?(?P<taskref>.+?)\s+to\s+"
    r"(?P<hours>\d+(?:\.\d+)?)\s*h(?:ours?)?",
    re.IGNORECASE,
)

_ESTIMATE_SHOULD_TAKE_RE = re.compile(
    r"(?P<taskref>.+?)\s+(?:should take|to)\s+(?P<hours>\d+(?:\.\d+)?)\s*h(?:ours?)?$",
    re.IGNORECASE,
)

_SPLIT_RE = re.compile(r"split\s+(?:task\s+)?(?P<taskref>.+)$", re.IGNORECASE)

_REMOVE_RE = re.compile(r"(?:remove|delete)\s+(?:task\s+)?(?P<taskref>.+)$", re.IGNORECASE)

_RENAME_RE = re.compile(
    r"rename\s+(?:task\s+)?(?P<taskref>.+?)\s+to\s+(?P<newtitle>.+)$",
    re.IGNORECASE,
)


def apply_instruction(plan: Plan, team: list[TeamMember], instruction: str) -> tuple[Plan, str]:
    """Parse `instruction` and apply the first recognized edit intent to a deep copy of plan.

    Never mutates the input plan. Returns (new_plan, note) where note
    describes what changed (or that nothing was recognized).
    """
    new_plan = plan.model_copy(deep=True)
    instruction = instruction.strip()

    match = _REASSIGN_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        who = match.group("who")
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        _, task = found
        member = _find_member(team, who)
        if member is None:
            return new_plan, f"No team member matching '{who}' found; plan unchanged."
        task.suggested_assignee = member.email
        return new_plan, f"Reassigned task '{task.title}' to {member.name} ({member.email})."

    match = _ESTIMATE_CHANGE_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        hours = float(match.group("hours"))
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        _, task = found
        old_hours = task.estimate_hours
        task.estimate_hours = hours
        return new_plan, f"Changed estimate for task '{task.title}' from {old_hours}h to {hours}h."

    match = _ESTIMATE_SHOULD_TAKE_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        hours = float(match.group("hours"))
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        _, task = found
        old_hours = task.estimate_hours
        task.estimate_hours = hours
        return new_plan, f"Changed estimate for task '{task.title}' from {old_hours}h to {hours}h."

    match = _SPLIT_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        epic, task = found
        half = max(1.0, task.estimate_hours / 2)
        part_a = Task(
            id=f"{task.id}a",
            title=f"{task.title} (part 1/2)",
            description=task.description,
            suggested_assignee=task.suggested_assignee,
            estimate_hours=half,
            skill_tag=task.skill_tag,
            depends_on=list(task.depends_on),
        )
        part_b = Task(
            id=f"{task.id}b",
            title=f"{task.title} (part 2/2)",
            description=task.description,
            suggested_assignee=task.suggested_assignee,
            estimate_hours=half,
            skill_tag=task.skill_tag,
            depends_on=list(task.depends_on),
        )
        idx = epic.tasks.index(task)
        epic.tasks[idx : idx + 1] = [part_a, part_b]
        return new_plan, f"Split task '{task.title}' into two tasks of {half}h each."

    match = _REMOVE_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        epic, task = found
        epic.tasks.remove(task)
        return new_plan, f"Removed task '{task.title}'."

    match = _RENAME_RE.search(instruction)
    if match:
        taskref = match.group("taskref")
        newtitle = match.group("newtitle").strip()
        found = _find_task(new_plan, taskref)
        if found is None:
            return new_plan, f"No task matching '{taskref}' found; plan unchanged."
        _, task = found
        old_title = task.title
        task.title = newtitle
        return new_plan, f"Renamed task '{old_title}' to '{newtitle}'."

    return new_plan, "No recognized edit in instruction; plan unchanged."


def diff_plans(old: Plan, new: Plan) -> str:
    """Unified diff of the two plans' JSON representations, as a single string."""
    old_text = json.dumps(old.model_dump(), indent=2, sort_keys=True).splitlines(keepends=True)
    new_text = json.dumps(new.model_dump(), indent=2, sort_keys=True).splitlines(keepends=True)
    diff = difflib.unified_diff(old_text, new_text, fromfile="current", tofile="proposed")
    return "".join(diff)
