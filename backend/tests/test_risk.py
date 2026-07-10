"""Unit coverage for compute_risk (deterministic, plain-Python risk scoring)."""

from app.models.plan import Epic, Plan, Task
from app.models.team import TeamMember
from app.services.risk import compute_risk


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


def test_empty_team_gives_max_score_and_high_severity():
    plan = _plan([_task("t1", "Backend", 4.0)])
    report = compute_risk(plan, [])
    assert report.score == 100
    assert report.level == "high"
    assert len(report.items) == 1
    assert report.items[0].skill == "(no team)"
    assert "AI-suggested risk summary" in report.narrative


def test_full_coverage_gives_low_score_and_no_items():
    plan = _plan([_task("t1", "Backend", 4.0), _task("t2", "Testing", 2.0)])
    team = [_member(skills="Backend, Testing")]
    report = compute_risk(plan, team)
    assert report.score == 0
    assert report.level == "low"
    assert report.items == []
    assert "coverage looks complete" in report.narrative


def test_uncovered_skill_gives_positive_score():
    plan = _plan([_task("t1", "Backend", 4.0), _task("t2", "Frontend", 6.0)])
    team = [_member(skills="Backend only")]
    report = compute_risk(plan, team)
    assert report.score > 0
    assert any(item.skill == "Frontend" for item in report.items)


def test_score_reflects_uncovered_hours_share():
    # 6 uncovered out of 10 total -> 60% -> score 60 -> high.
    plan = _plan([_task("t1", "Backend", 4.0), _task("t2", "Frontend", 6.0)])
    team = [_member(skills="Backend only")]
    report = compute_risk(plan, team)
    assert report.score == 60
    assert report.level == "high"


def test_severity_thresholds():
    # Small uncovered share -> low severity.
    plan = _plan([_task("t1", "Backend", 90.0), _task("t2", "Frontend", 10.0)])
    team = [_member(skills="Backend only")]
    report = compute_risk(plan, team)
    frontend_item = next(item for item in report.items if item.skill == "Frontend")
    assert frontend_item.severity == "low"


def test_no_skill_tags_at_all_gives_zero_score():
    plan = _plan([_task("t1", None, 4.0)])
    team = [_member()]
    report = compute_risk(plan, team)
    assert report.score == 0
    assert report.items == []


def test_zero_total_hours_guard_does_not_divide_by_zero():
    plan = Plan(epics=[])
    team = [_member()]
    report = compute_risk(plan, team)
    assert report.score == 0
    assert report.level == "low"


def test_determinism_repeated_calls_produce_identical_report():
    plan = _plan([_task("t1", "Backend", 4.0), _task("t2", "Frontend", 6.0)])
    team = [_member(skills="Backend only")]
    report1 = compute_risk(plan, team)
    report2 = compute_risk(plan, team)
    assert report1.model_dump() == report2.model_dump()
