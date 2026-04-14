import re
from datetime import datetime

REQUIRED_SECTION_KEYS = [
    "ai_news",
    "use_cases_and_deployments",
    "tools_and_practice",
    "weak_signals_and_trends",
    "research_and_breakthroughs",
    "education_and_pedagogy",
]

# Phase 5 / E1: allow ±2 paragraphs per section instead of exact count.
# Target counts stay as editorial blueprint but the LLM can miss one or two without failing.
EXPECTED_SECTION_COUNTS = {
    "ai_news": 5,
    "use_cases_and_deployments": 4,
    "tools_and_practice": 3,
    "weak_signals_and_trends": 2,
    "research_and_breakthroughs": 2,
    "education_and_pedagogy": 2,
}
SECTION_COUNT_TOLERANCE = 2  # ±2 per section, floor at 1

# Phase 5 / B4: default closing sentence is now just a fallback.
# The real value is loaded from `editorial.closing_sentence` in config/podcast.yaml
# and passed via `settings.closing_sentence` into assemble_script().
DEFAULT_CLOSING_SENTENCE = (
    "This podcast is sponsored by my novel, The Last Heaven — every copy bought on Amazon "
    "or at ashcroftedition.com pays for a week of production. Thank you."
)
# Backward-compat alias (tests and older callers import this name).
CLOSING_SENTENCE = DEFAULT_CLOSING_SENTENCE

INTRO_PATTERNS = {
    'daily': r"Your Daily AI Press Review — [A-Za-z]+ \d{2}, \d{4}: .+\.",
    'weekly': r"Your Weekly AI Press Review — Week of [A-Za-z]+ \d{2}, \d{4}: .+\.",
}


def build_intro_line(run_date: str, highlights_label: str, intro_format: str = 'daily') -> str:
    dt = datetime.fromisoformat(run_date)
    label = " ".join((highlights_label or "").split())[:32].strip() or "Highlights"
    if intro_format == 'weekly':
        formatted = dt.strftime("Week of %B %d, %Y")
        return f"Your Weekly AI Press Review — {formatted}: {label}."
    formatted = dt.strftime("%B %d, %Y")
    return f"Your Daily AI Press Review — {formatted}: {label}."


def _coerce_paragraph(item) -> str:
    """Normalise a paragraph to a plain string.

    Some LLMs (notably Claude) emit paragraphs as dicts — {"text": "..."} or
    {"content": "..."} — when given a schema whose values are strings. Rather
    than fail the whole run, extract the first string-typed value we can find.
    """
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("text", "content", "body", "paragraph", "value"):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for value in item.values():
            if isinstance(value, str) and value.strip():
                return value
    return str(item) if item is not None else ""


def _section_count_bounds(expected: int) -> tuple[int, int]:
    """Phase 5 / E1: ±SECTION_COUNT_TOLERANCE with a floor of 1 paragraph."""
    return max(1, expected - SECTION_COUNT_TOLERANCE), expected + SECTION_COUNT_TOLERANCE


def validate_section_payload(payload: dict) -> None:
    sections = payload.get("sections") or {}
    if list(sections.keys()) != REQUIRED_SECTION_KEYS:
        raise ValueError("Section order does not match the editorial line")

    for key in REQUIRED_SECTION_KEYS:
        paragraphs = sections.get(key)
        if not isinstance(paragraphs, list) or not paragraphs:
            raise ValueError(f"Missing section content for {key}")

        expected = EXPECTED_SECTION_COUNTS[key]
        min_count, max_count = _section_count_bounds(expected)
        actual = len(paragraphs)
        if not (min_count <= actual <= max_count):
            raise ValueError(
                f"Section {key} has {actual} paragraphs; expected {min_count}-{max_count} "
                f"(target {expected} ± {SECTION_COUNT_TOLERANCE})"
            )

        for paragraph in paragraphs:
            _validate_paragraph(_coerce_paragraph(paragraph))

    tomorrow_concept = (payload.get("tomorrow_pedagogical_concept") or "").strip()
    if not tomorrow_concept:
        raise ValueError("Tomorrow pedagogical concept is missing")
    if len(tomorrow_concept.split()) > 12:
        raise ValueError("Tomorrow pedagogical concept is too long")


def assemble_script(
    run_date: str,
    payload: dict,
    intro_format: str = 'daily',
    closing_sentence: str | None = None,
) -> str:
    validate_section_payload(payload)

    closing = (closing_sentence or DEFAULT_CLOSING_SENTENCE).strip()

    intro = build_intro_line(run_date, payload.get("highlights_label", "Highlights"), intro_format)
    sections = payload["sections"]

    ordered_paragraphs = [intro]
    for key in REQUIRED_SECTION_KEYS:
        normalised = [_coerce_paragraph(p).strip() for p in sections[key]]
        ordered_paragraphs.extend([p for p in normalised if p])

    ordered_paragraphs.append(closing)
    ordered_paragraphs.append(payload["tomorrow_pedagogical_concept"].strip().rstrip(".") + ".")

    script = "\n\n".join(ordered_paragraphs)
    validate_final_script(script, intro_format, closing_sentence=closing)
    return script


def validate_final_script(
    script: str,
    intro_format: str = 'daily',
    closing_sentence: str | None = None,
) -> None:
    closing = (closing_sentence or DEFAULT_CLOSING_SENTENCE).strip()

    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Script is empty")

    pattern = INTRO_PATTERNS.get(intro_format, INTRO_PATTERNS['daily'])
    if not re.fullmatch(pattern, lines[0]):
        raise ValueError("Opening line does not match the required format")

    if len(lines) < 4:
        raise ValueError("Script has too few paragraphs")

    if lines[-2] != closing:
        raise ValueError("Closing sentence does not exactly match the required line")

    tomorrow_line = lines[-1].lower()
    # Use first 4 words of the configured closing as a cheap signature to detect duplicate-closing-as-tomorrow
    closing_head = " ".join(closing.lower().split()[:4])
    if closing_head and tomorrow_line.startswith(closing_head):
        raise ValueError("Tomorrow pedagogical concept appears to be a duplicate of the closing sentence")

    for line in lines:
        _validate_paragraph(line)


def _validate_paragraph(text: str) -> None:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty paragraph found")
    if re.match(r"^[\-\*\u2022]\s+", stripped):
        raise ValueError("Bullet points are forbidden in the final script")
    if re.match(r"^\d+[\.)]\s+", stripped):
        raise ValueError("Enumerated lists are forbidden in the final script")
    if stripped.endswith(":"):
        raise ValueError("Heading-style paragraphs are forbidden in the final script")
