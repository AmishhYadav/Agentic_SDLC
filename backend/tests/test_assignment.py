"""Unit coverage for assign_plan (deterministic, skill-aware, load-balanced assignment)."""

from app.models.plan import Epic, Plan, Task
from app.models.team import TeamMember
from app.services.assignment import assign_plan


def _member(**overrides) -> TeamMember:
    fields = dict(
        id=None,
        name="Ada",
        email="ada@example.com",
        designation="Engineer",
        skills="Backend, Python",
        experience_level="mid",
    )
    fields.update(overrides)
    return TeamMember(**fields)


def _task(task_id: str, skill_tag: str | None, hours: float) -> Task:
    return Task(
        id=task_id,
        title=f"Task {task_id}",
        description="desc",
        suggested_assignee="",
        estimate_hours=hours,
        skill_tag=skill_tag,
    )


def _plan(tasks: list[Task]) -> Plan:
    return Plan(epics=[Epic(id="e1", title="Epic", description="desc", tasks=tasks)])


def test_empty_team_sets_all_assignees_to_empty_string():
    plan = _plan([_task("t1", "Backend", 4.0)])
    result = assign_plan(plan, [])
    assert result.epics[0].tasks[0].suggested_assignee == ""


def test_does_not_mutate_input_plan():
    plan = _plan([_task("t1", "Backend", 4.0)])
    team = [_member()]
    assign_plan(plan, team)
    assert plan.epics[0].tasks[0].suggested_assignee == ""


def test_skill_match_wins_over_non_match():
    plan = _plan([_task("t1", "Frontend", 4.0)])
    team = [
        _member(name="Backend Bob", email="bob@example.com", skills="Backend only"),
        _member(name="Frontend Fay", email="fay@example.com", skills="Frontend, React"),
    ]
    result = assign_plan(plan, team)
    assert result.epics[0].tasks[0].suggested_assignee == "fay@example.com"


def test_load_balancing_shifts_assignment_as_hours_accumulate():
    # Both members cover "Backend" equally (same experience level), so the
    # first task goes to whichever is picked by the tie-break (lowest load,
    # then name) — Alice sorts first alphabetically. The second Backend task
    # should then go to Bob, since Alice's load is now higher.
    plan = _plan(
        [
            _task("t1", "Backend", 10.0),
            _task("t2", "Backend", 10.0),
        ]
    )
    team = [
        _member(name="Alice", email="alice@example.com", skills="Backend"),
        _member(name="Bob", email="bob@example.com", skills="Backend"),
    ]
    result = assign_plan(plan, team)
    assignees = [t.suggested_assignee for t in result.epics[0].tasks]
    assert assignees[0] == "alice@example.com"
    assert assignees[1] == "bob@example.com"


def test_experience_level_breaks_ties_when_skills_equal():
    plan = _plan([_task("t1", "Backend", 4.0)])
    team = [
        _member(name="Junior Jan", email="jan@example.com", skills="Backend", experience_level="junior"),
        _member(name="Lead Lee", email="lee@example.com", skills="Backend", experience_level="lead"),
    ]
    result = assign_plan(plan, team)
    assert result.epics[0].tasks[0].suggested_assignee == "lee@example.com"


def test_deterministic_across_repeated_calls():
    plan = _plan(
        [
            _task("t1", "Backend", 4.0),
            _task("t2", "Frontend", 6.0),
            _task("t3", "Testing", 2.0),
        ]
    )
    team = [
        _member(name="Alice", email="alice@example.com", skills="Backend, Testing"),
        _member(name="Bob", email="bob@example.com", skills="Frontend"),
    ]
    result1 = assign_plan(plan, team)
    result2 = assign_plan(plan, team)
    assignees1 = [t.suggested_assignee for t in result1.epics[0].tasks]
    assignees2 = [t.suggested_assignee for t in result2.epics[0].tasks]
    assert assignees1 == assignees2


def test_none_skill_tag_treated_as_unmatched_for_everyone():
    plan = _plan([_task("t1", None, 4.0)])
    team = [_member(name="Alice", email="alice@example.com", skills="Backend")]
    result = assign_plan(plan, team)
    # Only one member -> still gets assigned even with no skill match.
    assert result.epics[0].tasks[0].suggested_assignee == "alice@example.com"
