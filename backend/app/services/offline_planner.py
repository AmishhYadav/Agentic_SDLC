"""Deterministic, offline (no-network) plan generator.

Used as the fallback plan-generation path when no NVIDIA_API_KEY is
configured (see app/services/llm.py's llm_available() and
app/graph/nodes/generate_plan.py), so the demo works end-to-end with zero
API keys. Produces a Plan grounded in docs_text via simple heuristics —
never calls an LLM, never touches the network. Must satisfy the same
constraints the LLM path enforces: 2-5 epics, 2-6 tasks each, valid taxonomy
skill_tags, positive estimates, empty suggested_assignee.
"""

import re

_GENERIC_EPICS = [
    "Foundation & Setup",
    "Core Features",
    "Integration & Delivery",
]

_ESTIMATE_CYCLE = [4, 6, 8, 12, 16]

_KEYWORD_SKILL_MAP: list[tuple[str, str]] = [
    ("test", "Testing"),
    ("api", "API-Design"),
    ("ui", "Frontend"),
    ("frontend", "Frontend"),
    ("page", "Frontend"),
    ("db", "Database"),
    ("data", "Database"),
    ("schema", "Database"),
    ("deploy", "DevOps"),
    ("ci", "DevOps"),
    ("auth", "Auth"),
    ("login", "Auth"),
    ("doc", "Documentation"),
]

_TASK_VERBS = ["Design", "Implement", "Validate", "Refine", "Document", "Harden"]


def _extract_seeds(docs_text: str) -> list[str]:
    """Pull heading-like or sentence-like seed strings out of docs_text.

    Prefers markdown headings (lines starting with '#'); falls back to
    non-empty lines/first sentences if there are too few headings. Always
    returns a (possibly empty) list of short, cleaned strings.
    """
    if not docs_text:
        return []

    lines = [line.strip() for line in docs_text.splitlines() if line.strip()]

    headings = []
    for line in lines:
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                headings.append(heading)

    if len(headings) >= 3:
        return headings

    seeds = list(headings)
    for line in lines:
        if line.startswith("#"):
            continue
        # Split on sentence boundaries to get short seed phrases.
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip(" -*#")
            if sentence:
                seeds.append(sentence)
        if len(seeds) >= 12:
            break

    return seeds


def _seed_title(seed: str, max_words: int = 8) -> str:
    words = seed.split()
    title = " ".join(words[:max_words])
    return title.strip(".,:;- ") or "General Work"


def _skill_for_title(title: str, taxonomy: list[str], index: int) -> str:
    lowered = title.lower()
    for keyword, skill in _KEYWORD_SKILL_MAP:
        if keyword in lowered and skill in taxonomy:
            return skill
    # Deterministic cycle through taxonomy for anything unmatched.
    return taxonomy[index % len(taxonomy)]


def _estimate_for_index(index: int) -> float:
    return float(_ESTIMATE_CYCLE[index % len(_ESTIMATE_CYCLE)])


def generate_plan_offline(docs_text: str, skill_taxonomy: list[str]) -> "Plan":
    """Produce a deterministic, valid Plan (3 epics, ~3 tasks each) from docs_text.

    Robust to empty/short docs_text — pads with generic engineering epics
    when there aren't enough seeds. No network calls anywhere in this
    function.
    """
    from app.models.plan import Epic, Plan, Task

    taxonomy = skill_taxonomy or ["Backend"]
    seeds = _extract_seeds(docs_text)

    epic_titles: list[str] = []
    for seed in seeds:
        title = _seed_title(seed, max_words=6)
        if title and title not in epic_titles:
            epic_titles.append(title)
        if len(epic_titles) >= 3:
            break

    for generic in _GENERIC_EPICS:
        if len(epic_titles) >= 3:
            break
        if generic not in epic_titles:
            epic_titles.append(generic)

    epic_titles = epic_titles[:3]

    # Extra seeds (beyond the ones used for epic titles) feed task titles.
    remaining_seeds = [s for s in seeds if _seed_title(s, 6) not in epic_titles]

    epics = []
    global_index = 0
    for epic_idx, epic_title in enumerate(epic_titles, start=1):
        epic_id = f"e{epic_idx}"
        tasks = []
        for task_idx in range(1, 4):
            task_id = f"{epic_id}-t{task_idx}"
            verb = _TASK_VERBS[global_index % len(_TASK_VERBS)]
            seed_pool_index = (epic_idx - 1) * 3 + (task_idx - 1)
            if seed_pool_index < len(remaining_seeds):
                seed_phrase = _seed_title(remaining_seeds[seed_pool_index], max_words=6)
            else:
                seed_phrase = epic_title
            title = f"{verb} {seed_phrase}"
            description = (
                f"{verb} work for '{epic_title}', grounded in project reference: "
                f"{seed_phrase}."
            )
            skill_tag = _skill_for_title(title, taxonomy, global_index)
            estimate_hours = _estimate_for_index(global_index)

            tasks.append(
                Task(
                    id=task_id,
                    title=title,
                    description=description,
                    suggested_assignee="",
                    estimate_hours=estimate_hours,
                    skill_tag=skill_tag,
                    depends_on=[],
                )
            )
            global_index += 1

        epics.append(
            Epic(
                id=epic_id,
                title=epic_title,
                description=f"Epic covering: {epic_title}.",
                tasks=tasks,
            )
        )

    return Plan(epics=epics)
