"""Free-text skill matching (D-06 reconciliation).

Team members enter skills as free text (never a list/enum). This module is
the single small, well-tested pure function that decides whether a fixed
taxonomy skill_tag (e.g. "API-Design") is "covered" by a member's free-text
skills string (e.g. "Python, REST APIs, Postgres").
"""


def _normalize(text: str) -> str:
    return text.lower().replace("-", " ")


def skill_covered_by(skill_tag: str, skills_text: str) -> bool:
    """Case-insensitive match of a taxonomy skill_tag against free-text skills.

    Normalizes both strings by lowercasing and replacing '-' with ' '. Matches
    if the normalized skill_tag appears as a substring of the normalized
    skills_text, OR if any whitespace token of the normalized skill_tag with
    len >= 3 appears as a substring of the normalized skills_text.
    """
    if not skill_tag or not skills_text:
        return False

    norm_skill = _normalize(skill_tag).strip()
    norm_text = _normalize(skills_text)

    if not norm_skill:
        return False

    if norm_skill in norm_text:
        return True

    for token in norm_skill.split():
        if len(token) >= 3 and token in norm_text:
            return True

    return False
