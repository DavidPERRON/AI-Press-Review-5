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

CLOSING_SENTENCE = (
    "This podcast has a daily production cost. If you'd like to support me, my latest book, The Last Heaven, is available on Amazon and at ashcroftedition.com — link on the podcast page. Thank you."
)

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


def validate_section_payload(payload: dict) -> None:
    sections = payload.get("sections") or {}
    if list(sections.keys()) != REQUIRED_SECTION_KEYS:
        raise ValueError("Section order does not match the editorial line")

    for key in REQUIRED_SECTION_KEYS:
        paragraphs = sections.get(key)
        if not isinstance(paragraphs, list) or not paragraphs:
            raise ValueError(f"Missing section content for {key}")
        for paragraph in paragraphs:
            _validate_paragraph(paragraph)

    tomorrow_concept = (payload.get("tomorrow_pedagogical_concept") or "").strip()
    if not tomorrow_concept:
        raise ValueError("Tomorrow pedagogical concept is missing")
    if len(tomorrow_concept.split()) > 12:
        raise ValueError("Tomorrow pedagogical concept is too long")


def assemble_script(run_date: str, payload: dict, intro_format: str = 'daily') -> str:
    validate_section_payload(payload)

    intro = build_intro_line(run_date, payload.get("highlights_label", "Highlights"), intro_format)
    sections = payload["sections"]

    ordered_paragraphs = [intro]
    for key in REQUIRED_SECTION_KEYS:
        ordered_paragraphs.extend([p.strip() for p in sections[key] if p.strip()])

    ordered_paragraphs.append(CLOSING_SENTENCE)
    ordered_paragraphs.append(payload["tomorrow_pedagogical_concept"].strip().rstrip(".") + ".")

    script = "\n\n".join(ordered_paragraphs)
    validate_final_script(script, intro_format)
    return script


def validate_final_script(script: str, intro_format: str = 'daily') -> None:
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Script is empty")

    pattern = INTRO_PATTERNS.get(intro_format, INTRO_PATTERNS['daily'])
    if not re.fullmatch(pattern, lines[0]):
        raise ValueError("Opening line does not match the required format")

    if len(lines) < 4:
        raise ValueError("Script has too few paragraphs")

    if lines[-2] != CLOSING_SENTENCE:
        raise ValueError("Closing sentence does not exactly match the required line")

    tomorrow_line = lines[-1].lower()
    if tomorrow_line.startswith("this podcast has"):
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
