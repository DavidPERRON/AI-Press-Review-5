from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

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

    target_words = max(settings.min_script_words + 800, 3000)

    schema = {
        "episode_title": "string — max 60 chars. Format: '[Primary keyword]: [tension or outcome] — [Mon DD]'. Lead with the most searchable noun (company, technology, domain). Include implicit tension. No episode number. No year. No 'Episode', no 'Daily', no 'AI Briefing' prefix. Examples: 'OpenAI o4 vs. Gemini 2.5: who wins enterprise — Apr 12', 'Meta's open-source bet: competitive move or PR? — Apr 13'.",
        "episode_summary": "string — 2-3 sentence summary of the episode",
        "opening_news_title": "string — the most impactful headline of the day",
        "highlights_label": "1-2 words summarizing the day's theme",
        "tomorrow_pedagogical_concept": "one short sentence fragment, no more than 12 words, announcing a concept to explain tomorrow",
        "key_claims": [
            "array of 8-15 objects, one per factual claim made in the script that cites a specific number, company, product, or verifiable event. Each object MUST have exactly two keys: 'claim' (short factual statement, 12-25 words, as stated in the script) and 'source_url' (one of the manifest's source URLs that supports this claim — copy verbatim from the manifest). Example: {'claim': 'OpenAI released a new model that outperforms prior systems on reasoning benchmarks', 'source_url': 'https://openai.com/blog/...'}. Only include claims that are directly supported by at least one cited source.",
        ],
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
    # In multi-pass mode, the pre-computed story ledger is prepended so
    # the writer works from a curated running order rather than raw sources.
    if manifest.get("story_ledger"):
        payload["story_ledger"] = manifest["story_ledger"]
        payload["instructions"] += (
            " A structured STORY_LEDGER has been produced by a research pass and is "
            "provided below. Use it as the running order — each story in the ledger "
            "should become a paragraph (or part of one) in the appropriate pillar. "
            "Do NOT introduce topics absent from the ledger."
        )
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
        raise ValueError(f"Connection error: {exc}") from exc

    if response.status_code >= 400:
        raise ValueError(f"HTTP {response.status_code}: {_response_error_text(response)}")

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
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise ValueError(f"Model did not return valid JSON. First 500 chars: {content[:500]}")
        return json.loads(match.group(0))


def _cacheable_text(content: str) -> list[dict[str, Any]]:
    """Mark a message content block as cache-eligible. OpenAI-compatible
    gateways with Anthropic underneath (OpenRouter, LiteLLM, Anthropic
    direct) honor `cache_control: {type: "ephemeral"}`. Gateways that
    don't understand it simply treat it as plain text."""
    return [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]


def _generate_with_model(model: str, manifest: dict, settings, force_length: bool) -> dict[str, Any]:
    from ..observability import record_llm_call

    system_text = settings.prompt_path.read_text(encoding="utf-8")
    user_text = _build_user_prompt(manifest, settings, force_length=force_length)

    if getattr(settings, 'llm_enable_prompt_cache', False):
        # Cache system prompt (stable across all runs) and the manifest
        # block (stable across retries on the same run). The only part
        # that changes between retries is the "too short" addendum —
        # which is NOT marked cacheable.
        messages = [
            {"role": "system", "content": _cacheable_text(system_text)},
            {"role": "user", "content": _cacheable_text(user_text)},
        ]
    else:
        messages = [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ]

    start = time.monotonic()
    success = False
    usage: dict[str, Any] = {}
    try:
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

        usage = data.get("usage", {}) or {}
        logger.info(
            "LLM call completed: model=%s elapsed=%.1fs prompt_tokens=%s completion_tokens=%s",
            model, elapsed,
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
        )
        payload = _extract_json(content)
        success = True
        return payload
    finally:
        elapsed = time.monotonic() - start
        # Anthropic returns cache_read_input_tokens in usage; OpenAI returns
        # cached_tokens nested under prompt_tokens_details.
        cached = (
            usage.get("cache_read_input_tokens")
            or usage.get("prompt_tokens_details", {}).get("cached_tokens")
            or 0
        )
        record_llm_call(
            run_date=manifest.get("run_date", "unknown"),
            model=model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            cached_tokens=int(cached or 0),
            duration_s=elapsed,
            phase="editorial",
            success=success,
            force_length=force_length,
        )


def _maybe_run_ledger_pass(manifest: dict, settings) -> dict:
    """If editorial_mode='multi_pass', run the ledger pass and attach its
    output to the manifest so the writer receives it. Returns the manifest
    (possibly enriched) — always safe to call.
    """
    if getattr(settings, 'editorial_mode', 'single_pass') != 'multi_pass':
        return manifest
    try:
        from .passes import run_ledger_pass
        ledger = run_ledger_pass(
            manifest, settings,
            post_chat_completion=_post_chat_completion,
            extract_message_content=_extract_message_content,
            extract_json=_extract_json,
            enable_cache=getattr(settings, 'llm_enable_prompt_cache', True),
        )
        # Enrich the manifest: the user prompt builder appends story_ledger
        # if present.
        enriched = dict(manifest)
        enriched['story_ledger'] = ledger
        return enriched
    except Exception as exc:
        logger.warning("Ledger pass failed, falling back to single-pass: %s", exc)
        return manifest


@retry(wait=wait_fixed(3), stop=stop_after_attempt(2))
def generate_episode_script(manifest: dict, local_preview: bool = False, profile: str | None = None) -> EpisodeDraft:
    settings = load_settings(local_preview=local_preview, profile=profile)

    source_count = manifest.get("source_count", 0)
    if source_count < settings.min_source_count:
        raise ValueError(
            f"Not enough relevant sources: {source_count} < {settings.min_source_count}"
        )

    # Optional ledger pass enriches the manifest before the writer runs.
    manifest = _maybe_run_ledger_pass(manifest, settings)

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

            # Claim grounding: verify that each claim the LLM cited is
            # actually supported by its declared source.
            from .grounding import verify_claims

            raw_claims = best_payload.get("key_claims") or []
            report = verify_claims(
                raw_claims,
                manifest.get("sources", []),
                min_overlap_ratio=float(getattr(settings, 'grounding_min_overlap', 0.55)),
                min_coverage_ratio=float(getattr(settings, 'grounding_min_coverage', 0.7)),
            )

            return EpisodeDraft(
                episode_title=best_payload.get("episode_title", settings.podcast_title),
                episode_summary=best_payload.get("episode_summary", settings.podcast_description_short),
                opening_news_title=best_payload.get("opening_news_title", ""),
                script=best_script,
                tomorrow_concept=best_payload.get("tomorrow_pedagogical_concept", ""),
                highlights_label=best_payload.get("highlights_label", "Highlights"),
                key_claims=raw_claims if isinstance(raw_claims, list) else [],
                grounding_report=report.to_dict(),
            )
        except Exception as exc:
            logger.error("Model %s failed: %s", model, exc)
            errors.append(f"{model}: {exc}")

    raise ValueError("All editorial generation attempts failed: " + " | ".join(errors))
