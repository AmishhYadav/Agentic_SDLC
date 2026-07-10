"""Unit coverage for apply_instruction (offline NL plan editing) and diff_plans."""

from app.models.plan import Epic, Plan, Task
from app.models.team import TeamMember
from app.services.plan_edit import apply_instruction, diff_plans


def _member(**overrides) -> TeamMember:
    fields = dict(
        id=None,
        name="Ada Lovelace",
        email="ada@example.com",
        designation="Engineer",
        skills="Backend",
        experience_level="mid",
    )
    fields.update(overrides)
    return TeamMember(**fields)


def _task(task_id: str, title: str, hours: float = 4.0, skill_tag: str | None = "Backend") -> Task:
    return Task(
        id=task_id,
        title=title,
        description="desc",
        suggested_assignee="",
        estimate_hours=hours,
        skill_tag=skill_tag,
    )


def _plan() -> Plan:
    return Plan(
        epics=[
            Epic(
                id="e1",
                title="Epic One",
                description="desc",
                tasks=[
                    _task("e1-t1", "Build login page"),
                    _task("e1-t2", "Write integration tests", hours=6.0),
                ],
            )
        ]
    )


def test_reassign_sets_suggested_assignee():
    plan = _plan()
    team = [_member(name="Ada Lovelace", email="ada@example.com")]
    new_plan, note = apply_instruction(plan, team, "assign login page to Ada")
    assert new_plan.epics[0].tasks[0].suggested_assignee == "ada@example.com"
    assert "Ada" in note
    # Input not mutated.
    assert plan.epics[0].tasks[0].suggested_assignee == ""


def test_reassign_member_not_found_leaves_plan_unchanged():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "reassign login page to Bob")
    assert new_plan.epics[0].tasks[0].suggested_assignee == ""
    assert "No team member matching" in note


def test_estimate_change_with_change_estimate_phrasing():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "change the estimate for login page to 10 hours")
    assert new_plan.epics[0].tasks[0].estimate_hours == 10.0
    assert "10.0h" in note


def test_estimate_change_with_should_take_phrasing():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "login page should take 8h")
    assert new_plan.epics[0].tasks[0].estimate_hours == 8.0


def test_split_task_creates_two_half_hour_tasks():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "split integration tests")
    tasks = new_plan.epics[0].tasks
    assert len(tasks) == 3
    split_titles = [t.title for t in tasks if "part" in t.title]
    assert len(split_titles) == 2
    split_tasks = [t for t in tasks if "part" in t.title]
    assert all(t.estimate_hours == 3.0 for t in split_tasks)
    assert "Split task" in note


def test_split_task_minimum_one_hour_floor():
    plan = Plan(
        epics=[
            Epic(
                id="e1",
                title="E",
                description="d",
                tasks=[_task("e1-t1", "Tiny task", hours=1.0)],
            )
        ]
    )
    new_plan, _ = apply_instruction(plan, [], "split tiny task")
    for task in new_plan.epics[0].tasks:
        assert task.estimate_hours >= 1.0


def test_remove_task_drops_it_from_epic():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "remove login page")
    titles = [t.title for t in new_plan.epics[0].tasks]
    assert "Build login page" not in titles
    assert len(new_plan.epics[0].tasks) == 1
    assert "Removed task" in note


def test_delete_synonym_also_works():
    plan = _plan()
    new_plan, _ = apply_instruction(plan, [], "delete login page")
    assert len(new_plan.epics[0].tasks) == 1


def test_rename_task_changes_title():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "rename login page to Build signup page")
    assert new_plan.epics[0].tasks[0].title == "Build signup page"
    assert "Renamed task" in note


def test_no_match_returns_unchanged_copy_with_note():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "do something incomprehensible")
    assert new_plan.model_dump() == plan.model_dump()
    assert note == "No recognized edit in instruction; plan unchanged."


def test_task_not_found_returns_helpful_note():
    plan = _plan()
    new_plan, note = apply_instruction(plan, [], "remove nonexistent task")
    assert "No task matching" in note


def test_diff_plans_empty_when_no_change():
    plan = _plan()
    diff = diff_plans(plan, plan.model_copy(deep=True))
    assert diff == ""


def test_diff_plans_non_empty_on_change():
    plan = _plan()
    new_plan, _ = apply_instruction(plan, [], "remove login page")
    diff = diff_plans(plan, new_plan)
    assert diff != ""
    assert "current" in diff
    assert "proposed" in diff
