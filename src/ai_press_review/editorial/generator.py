from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from ..models import EpisodeDraft
from ..settings import load_settings
from .validate import assemble_script

logger = logging.getLogger(__name__)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _build_user_prompt(manifest: dict, settings, force_length: bool = False) -> str:
    compact_sources = []
    for src in manifest.get("sources", [])[:120]:
        compact_sources.append(
            {
                "title": src.get("title"),
                "domain": src.get("domain"),
                "url": src.get("url"),
                "published_at": src.get("published_at"),
                "summary": src.get("summary"),
                "content_text": (src.get("content_text") or "")[:2200],
                "relevance_score": src.get("relevance_score", 0.0),
            }
        )

    # Schema ceiling: 18 paragraphs × 150 max words + intro/closing ≈ 2769 words.
    # Target below ceiling to keep instruction realistic for the LLM.
    target_words = min(max(settings.min_script_words + 300, 2400), 2700)

    schema = {
        "episode_title": "string — short, factual, no clickbait",
        "episode_summary": "string — 2-3 sentence summary of the episode",
        "opening_news_title": "string — the most impactful headline of the day",
        "highlights_label": "1-2 words summarizing the day's theme",
        "tomorrow_pedagogical_concept": "one short sentence fragment, no more than 12 words, announcing a concept to explain tomorrow",
        "sections": {
            "ai_news": [
                "paragraph 1 (110-150 words): lead story — set the scene, why it matters now",
                "paragraph 2 (110-150 words): second major story, bridge naturally from the first",
                "paragraph 3 (110-150 words): third story — partnership, funding, or company move",
                "paragraph 4 (110-150 words): fourth story, connect to a broader theme if possible",
                "paragraph 5 (110-150 words): fifth story or follow-up on a developing trend",
            ],
            "use_cases_and_deployments": [
                "paragraph 1 (110-150 words): most impactful deployment — what changed in practice",
                "paragraph 2 (110-150 words): second deployment with measurable business gains",
                "paragraph 3 (110-150 words): third use case — different industry or scale",
                "paragraph 4 (110-150 words): adoption pattern or what these deployments have in common",
            ],
            "tools_and_practice": [
                "paragraph 1 (110-150 words): most notable tool — what can someone do now that they couldn't before",
                "paragraph 2 (110-150 words): practical technique or workflow change",
                "paragraph 3 (110-150 words): additional tool or ecosystem shift worth knowing",
            ],
            "weak_signals_and_trends": [
                "paragraph 1 (110-150 words): emerging pattern grounded in multiple cited facts",
                "paragraph 2 (110-150 words): forward-looking observation — connect the dots across stories",
            ],
            "research_and_breakthroughs": [
                "paragraph 1 (110-150 words): ONE breakthrough explained simply — what was achieved and why it matters",
                "paragraph 2 (110-150 words): second result only if truly significant — keep it accessible",
            ],
            "education_and_pedagogy": [
                "paragraph 1 (110-150 words): one concept explained with a concrete analogy",
                "paragraph 2 (110-150 words): why it matters in practice — make the listener feel smarter",
            ],
        },
    }

    length_instructions = (
        f"Your script MUST contain at least {settings.min_script_words} words total. "
        f"Target {target_words} words. "
        "Each paragraph MUST be between 110 and 150 words — never shorter than 110 words. "
        "Write ALL 18 paragraphs listed in the schema. Do NOT skip any. "
    )

    if force_length:
        length_instructions += (
            "CRITICAL: Your previous output was TOO SHORT. You MUST write longer paragraphs "
            "and add more detail to every section. Include additional concrete facts, specific "
            "numbers, model names, benchmark scores, company names, deployment scales, and "
            "explanations accessible to non-experts. Do NOT summarize aggressively. "
            "Every section must be substantial and dense with information. "
        )

    # Weekly recap context
    if settings.profile_name == 'weekly_recap':
        length_instructions += (
            "This is a WEEKLY RECAP covering the entire past week. "
            "Prioritize the biggest stories that generated buzz. "
            "Also highlight important news that may have been missed in daily episodes. "
            "Sources with higher relevance_score are more likely to be unused — prioritize them. "
            "Use natural time references when covering stories from different days. "
        )

    payload = {
        "constraints": {
            "title": settings.podcast_title,
            "subtitle": settings.podcast_subtitle,
            "target_duration_min": settings.target_duration_min,
            "target_duration_max": settings.target_duration_max,
            "minimum_script_words": settings.min_script_words,
            "target_script_words": target_words,
            "min_source_count": settings.min_source_count,
            "required_output": schema,
        },
        "instructions": (
            "Return JSON only. Do not include markdown fences or any text outside the JSON. "
            "Write as a confident radio host — natural, engaging, conversational but professional. "
            "No bullet points. No headings inside paragraphs. "
            "NUMBERS: Round aggressively (say 'about 1.2 billion' not '1,247,000,000'). "
            "Skip model version numbers (say 'the latest GPT' not 'GPT-4o-2024-05-13'). "
            "FLOW: Connect stories naturally. Never say 'Moving on' or 'In our next section'. "
            "Use callbacks to earlier stories when relevant. Bridge between topics seamlessly. "
            "RHYTHM: Vary sentence length. Short after complex. Use dashes and commas for pauses. "
            "Use contractions (it's, they've, that's). Write for the ear, not the eye. "
            "Prioritize sources with the highest relevance_score. "
            "Cross-reference multiple sources on the same topic to build richer paragraphs. "
            + length_instructions
        ).strip(),
        "source_manifest": compact_sources,
    }
    return json.dumps(payload, ensure_ascii=False)


def _response_error_text(response: requests.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            if isinstance(data.get("error"), dict):
                return str(data["error"].get("message") or data["error"])
            return str(data)
    except Exception:
        pass
    return response.text.strip()[:500]


def _extract_message_content(data: dict[str, Any]) -> str:
    try:
        message = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise ValueError(f"Malformed LLM response: {data}") from exc

    if isinstance(message, str):
        return message

    if isinstance(message, list):
        parts: list[str] = []
        for item in message:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts).strip()

    return str(message).strip()


def _post_chat_completion(settings, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = (settings.llm_base_url or "").strip().rstrip("/")
    if not base_url.startswith("http"):
        raise ValueError(f"Invalid LLM_BASE_URL: {base_url!r}")
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0") or hostname.startswith("169.254.") or hostname.startswith("10.") or hostname.startswith("192.168."):
        raise ValueError(f"LLM_BASE_URL points to a private/internal address: {base_url!r}")

    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=max(settings.llm_timeout_seconds, 180),
        )
    except requests.RequestException as exc:
        raise ValueError(f"LLM connection error to {parsed.hostname}") from exc

    if response.status_code >= 400:
        raise ValueError(f"LLM HTTP {response.status_code}: {_response_error_text(response)}")

    try:
        return response.json()
    except Exception as exc:
        raise ValueError(f"LLM returned non-JSON response: {response.text[:500]}") from exc


def _create_completion_data(
    settings,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    try:
        return _post_chat_completion(settings, payload)
    except Exception as exc:
        message = str(exc).lower()
        if "json_object" in message or "response format" in message or "405" in message:
            logger.info("Model does not support response_format, retrying without it")
            payload.pop("response_format", None)
            return _post_chat_completion(settings, payload)
        raise


def _extract_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Find the outermost JSON object by matching braces
        start = cleaned.find("{")
        if start == -1:
            raise ValueError(f"Model did not return valid JSON. First 500 chars: {content[:500]}")
        depth = 0
        for i, ch in enumerate(cleaned[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start:i + 1])
                    except json.JSONDecodeError:
                        break
        raise ValueError(f"Model did not return valid JSON. First 500 chars: {content[:500]}")


def _generate_with_model(model: str, manifest: dict, settings, force_length: bool) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": settings.prompt_path.read_text(encoding="utf-8")},
        {"role": "user", "content": _build_user_prompt(manifest, settings, force_length=force_length)},
    ]

    start = time.monotonic()
    data = _create_completion_data(
        settings=settings,
        model=model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
    elapsed = time.monotonic() - start

    content = _extract_message_content(data)
    if not content.strip():
        raise ValueError("Model returned empty content")

    usage = data.get("usage", {})
    logger.info(
        "LLM call completed: model=%s elapsed=%.1fs prompt_tokens=%s completion_tokens=%s",
        model, elapsed,
        usage.get("prompt_tokens", "?"),
        usage.get("completion_tokens", "?"),
    )

    return _extract_json(content)


def generate_episode_script(manifest: dict, local_preview: bool = False, profile: str | None = None) -> EpisodeDraft:
    settings = load_settings(local_preview=local_preview, profile=profile)

    source_count = manifest.get("source_count", 0)
    if source_count < settings.min_source_count:
        raise ValueError(
            f"Not enough relevant sources: {source_count} < {settings.min_source_count}"
        )

    errors: list[str] = []

    models = [settings.llm_editor_model]
    if settings.llm_fallback_model:
        models.append(settings.llm_fallback_model)

    max_length_retries = 4  # nombre de tentatives par modele si trop court

    for model in models:
        try:
            logger.info("Generating script with model: %s (profile=%s)", model, settings.profile_name)

            best_payload = None
            best_script = None
            best_wc = 0

            for attempt in range(max_length_retries):
                force = attempt > 0
                logger.info("Attempt %d/%d (force_length=%s)", attempt + 1, max_length_retries, force)

                try:
                    payload = _generate_with_model(model, manifest, settings, force_length=force)
                    script = assemble_script(manifest["run_date"], payload, intro_format=settings.intro_format)
                    wc = _word_count(script)
                except Exception as inner_exc:
                    logger.warning("Attempt %d failed: %s", attempt + 1, inner_exc)
                    continue

                logger.info("Attempt %d produced %d words", attempt + 1, wc)

                if wc > best_wc:
                    best_payload = payload
                    best_script = script
                    best_wc = wc

                if wc >= settings.min_script_words:
                    break

                logger.warning(
                    "Script too short: %d words < %d minimum, retrying...",
                    wc, settings.min_script_words,
                )

            if best_wc < settings.min_script_words:
                raise ValueError(
                    f"Script too short after {max_length_retries} attempts: "
                    f"{best_wc} words < {settings.min_script_words} minimum"
                )

            logger.info("Script generated successfully: %d words, model=%s", best_wc, model)
            return EpisodeDraft(
                episode_title=best_payload.get("episode_title", settings.podcast_title),
                episode_summary=best_payload.get("episode_summary", settings.podcast_description_short),
                opening_news_title=best_payload.get("opening_news_title", ""),
                script=best_script,
                tomorrow_concept=best_payload.get("tomorrow_pedagogical_concept", ""),
                highlights_label=best_payload.get("highlights_label", "Highlights"),
            )
        except Exception as exc:
            logger.error("Model %s failed: %s", model, exc)
            errors.append(f"{model}: {exc}")

    raise ValueError("All editorial generation attempts failed: " + " | ".join(errors))
