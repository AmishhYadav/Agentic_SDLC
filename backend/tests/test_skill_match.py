"""Unit coverage for skill_covered_by (free-text skill matching, D-06 reconciliation)."""

from app.services.skill_match import skill_covered_by


def test_exact_substring_match_case_insensitive():
    assert skill_covered_by("Backend", "Strong BACKEND engineer") is True


def test_hyphenated_skill_tag_matches_space_separated_skills_text():
    assert skill_covered_by("API-Design", "experience with api design and REST") is True


def test_token_match_when_full_phrase_not_present():
    assert skill_covered_by("Data-Engineering", "background in engineering pipelines") is True


def test_short_tokens_under_three_chars_are_not_matched_alone():
    # "ux" as a skill_tag token has len 2, should not match via bare token rule,
    # but the full normalized phrase "ux design" not present either -> no match.
    assert skill_covered_by("UX-Design", "Python, Go, SQL") is False


def test_no_match_returns_false():
    assert skill_covered_by("Frontend", "Postgres, database tuning") is False


def test_empty_skill_tag_returns_false():
    assert skill_covered_by("", "Python, Frontend") is False


def test_empty_skills_text_returns_false():
    assert skill_covered_by("Backend", "") is False


def test_case_and_hyphen_normalization_both_sides():
    assert skill_covered_by("devops", "DevOps and CI/CD pipelines") is True
