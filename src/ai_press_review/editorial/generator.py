from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

import requests

from ..models import EpisodeDraft
from ..settings import load_settings
from .validate import assemble_script

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Typed exception hierarchy
# ─────────────────────────────────────────────────────────────────────────────
#
# 2026-04-16: production crashed because the retry loop treated every failure
# the same. Quota exhaustion (HTTP 429) burned all 4 attempts in ~5 seconds
# because we used `wait_fixed(3)` instead of respecting `Retry-After`. Then
# the misleading message "Script too short: 0 words" hid the real cause.
#
# Splitting the failure modes lets the loop:
#   • Pause appropriately on quota — long, jittered, capped wait.
#   • Pause briefly on transient 5xx — exponential backoff.
#   • Switch model immediately on quota that won't recover within budget.
#   • Skip retry entirely on validation errors that will never get better
#     by waiting (malformed JSON from same prompt, etc.).
class LLMError(Exception):
    """Base class for editorial LLM call failures."""


class LLMQuotaError(LLMError):
    """HTTP 429 / explicit quota signal. Carries Retry-After hint when present."""

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMTransientError(LLMError):
    """HTTP 5xx, connection drop, or timeout. Worth a backed-off retry."""


class LLMInvalidResponseError(LLMError):
    """Model returned malformed JSON or empty content. A single retry only."""


class LLMShortScriptError(LLMError):
    """Script came back under min_script_words. Retry with force_length=True."""

    def __init__(self, message: str, word_count: int) -> None:
        super().__init__(message)
        self.word_count = word_count


# HTTP status code groups
_QUOTA_HTTP_CODES = (429,)
_TRANSIENT_HTTP_CODES = (500, 502, 503, 504)


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

    target_words = max(settings.min_script_words + 400, 2500)

    schema = {
        "episode_title": "string — short, factual, no clickbait",
        "episode_summary": "string — 2-3 sentence summary of the episode",
        "opening_news_title": "string — the most impactful headline of the day",
        "highlights_label": "1-2 words summarizing the day's theme",
        "tomorrow_pedagogical_concept": "one short sentence fragment, no more than 12 words, announcing a concept to explain tomorrow",
        "sections": {
            # IMPORTANT: variable paragraph count per section. One paragraph = ONE
            # distinct story/fact. Do NOT pad. Do NOT write synthesis paragraphs
            # that recombine facts already stated elsewhere. If a fact only fills
            # 60 words cleanly, write 60 and move on — never stretch to hit a quota.
            "ai_news": [
                "5 to 8 paragraphs of 80-110 words each. ONE story per paragraph: launch, partnership, funding, or major corporate move. Lead with the biggest of the day. No transitions between stories inside this section — end one, start the next.",
            ],
            "use_cases_and_deployments": [
                "4 to 6 paragraphs of 80-110 words each. ONE deployment per paragraph — who deployed what, on what scale, with what measurable result. Prefer numbers (revenue %, latency ms, users, cost delta).",
            ],
            "tools_and_practice": [
                "3 to 5 paragraphs of 80-110 words each. ONE tool or technique per paragraph — what a practitioner can now do that they couldn't yesterday, with the name of the tool and the concrete capability.",
            ],
            "weak_signals_and_trends": [
                "1 to 2 paragraphs of 80-110 words each. ONE concrete signal per paragraph, each grounded in AT LEAST TWO distinct cited facts (different companies, different domains, or different papers). NEVER a synthesis of what you already said in the previous sections. If you have no genuine signal, write only one paragraph and keep it tight.",
            ],
            "research_and_breakthroughs": [
                "2 to 4 paragraphs of 80-110 words each. ONE result per paragraph — paper title or lab, what was achieved (one concrete number or comparison), and why it matters in one sentence. No method explanation unless a finance exec could not otherwise understand the result.",
            ],
            "education_and_pedagogy": [
                "exactly 2 paragraphs of 80-110 words each. Paragraph 1: one concept introduced with a concrete analogy. Paragraph 2: why the concept matters in practice today — tie to ONE of the stories covered earlier. No third paragraph.",
            ],
        },
    }

    length_instructions = (
        f"Your script MUST contain at least {settings.min_script_words} words total across all paragraphs. "
        f"Target {target_words} words. The range you are aiming for is 14 to 18 spoken minutes. "
        "Each paragraph MUST be between 80 and 110 words. Never shorter than 80. Never longer than 110. "
        "Each paragraph covers ONE distinct story or fact — one story per paragraph, never merge two into one, never split one across two. "
        "If a story only carries 60 words of actual substance, DO NOT stretch it. Pick another story from the manifest instead. "
        "Produce between 18 and 28 paragraphs total across all sections, distributed per the schema ranges. "
        "Hitting the word target comes from COVERING MORE STORIES, not from inflating paragraphs. "
    )

    if force_length:
        length_instructions += (
            "CRITICAL: Your previous output was TOO SHORT. You MUST cover MORE distinct stories "
            "from the source manifest. Do NOT lengthen existing paragraphs. Do NOT add synthesis "
            "paragraphs. Add NEW paragraphs each covering a NEW story with its own facts: company "
            "name, number, product name, or result. Dig deeper into the manifest — there are 120 "
            "sources there, use them. "
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
            "TONE: You are a press analyst writing for busy senior professionals, in the register of "
            "Stratechery or Les Echos Briefing — NOT a radio host. Fact → number → concrete consequence "
            "in one action verb. The listener draws the lesson; you never draw it for them. "
            "No bullet points. No headings inside paragraphs. "
            "DENSITY (hard rule): Every paragraph must contain at least TWO distinct numbers OR at least "
            "TWO distinct proper nouns (company, product, researcher, country, dataset, paper). "
            "If a story cannot carry that density, pick another story from the manifest. "
            "FORBIDDEN: meta-commentary ('this matters because', 'this shows that', 'pour les entreprises, "
            "ça signifie que'), generic management lessons ('don't bet on one horse', 'without adoption, "
            "the best model stays unused'), forward-looking platitudes ('this opens the way to', 'it's a "
            "key step', 'ça ouvre la voie à'), synthesis paragraphs that recombine earlier facts without "
            "adding new ones, and restating a story in a later section. "
            "NO RECYCLING: A fact, company, product, or study may be cited in ONE paragraph only across "
            "the entire script. Callbacks by single-name reference ('as Meta showed') are allowed only "
            "in the education section, never elsewhere. "
            "NUMBERS: Round aggressively ('about 1.2 billion' not '1,247,000,000'). Skip model version "
            "numbers ('the latest GPT' not 'GPT-4o-2024-05-13'). "
            "ACRONYMS: Write them in their canonical uppercase form (TSMC, GPT, API, LLM, IA, PDG, IPO, USA). "
            "The TTS layer normalizes them to the correct spoken form, so DO NOT pre-spell them out, DO NOT "
            "expand them mid-sentence ('graphics processing units — or GPUs'), and DO NOT add letter-by-letter "
            "hints. Just write the acronym once in its canonical form and reuse it. "
            "FLOW: Within a pillar, no transitions between stories — end one paragraph, start the next with "
            "the next story's subject. "
            "PILLAR SIGNPOSTS: The first paragraph of every pillar after AI News opens with a SHORT factual "
            "signpost of 3 to 6 words, then a period, then the first fact. Examples (FR): 'Côté déploiements.' / "
            "'Côté outils.' / 'Un signal à surveiller.' / 'Côté recherche.' / 'Un concept à retenir.' (EN: "
            "'Turning to deployments.' / 'On tools.' / 'One signal to watch.' / 'On the research front.' / "
            "'One concept to keep.'). Never speak the pillar name itself. Never use pontificating bridges "
            "like 'Pulling back from the day's news, a few patterns are worth flagging' — this is dead air. "
            "RHYTHM: Vary sentence length. Short sentences are allowed and encouraged. Use dashes and commas "
            "for pauses. Use contractions (it's, they've, ca, c'est, on). Write for the ear, not the eye. "
            "Prioritize sources with the highest relevance_score. Cross-reference multiple sources on the "
            "same topic to sharpen a single paragraph's facts, not to create extra paragraphs. "
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


def _parse_retry_after(response: requests.Response) -> float | None:
    """Parse Retry-After header. Returns seconds-to-wait, or None if absent/invalid.

    Per RFC 7231 the value is either delta-seconds (an integer) or an HTTP-date.
    Most LLM gateways send seconds; we cap at 120s so a stuck retry doesn't
    block a daily run forever.
    """
    raw = response.headers.get('Retry-After') or response.headers.get('retry-after')
    if not raw:
        return None
    try:
        seconds = float(raw.strip())
    except (TypeError, ValueError):
        # HTTP-date format — rare from LLM APIs; treat as "no hint"
        return None
    if seconds < 0:
        return None
    return min(seconds, 120.0)


def _extract_message_content(data: dict[str, Any]) -> str:
    try:
        message = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMInvalidResponseError(f"Malformed LLM response: {data}") from exc

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
        raise LLMTransientError(f"LLM connection error to {parsed.hostname}: {exc}") from exc

    status = response.status_code
    if status in _QUOTA_HTTP_CODES:
        retry_after = _parse_retry_after(response)
        raise LLMQuotaError(
            f"LLM HTTP {status} (quota exhausted): {_response_error_text(response)}",
            retry_after_s=retry_after,
        )
    if status in _TRANSIENT_HTTP_CODES:
        raise LLMTransientError(
            f"LLM HTTP {status} (transient): {_response_error_text(response)}"
        )
    if status >= 400:
        # Permanent client error (400/401/403/404/422/etc.) — do not retry
        raise ValueError(f"LLM HTTP {status}: {_response_error_text(response)}")

    try:
        return response.json()
    except Exception as exc:
        raise LLMInvalidResponseError(
            f"LLM returned non-JSON response: {response.text[:500]}"
        ) from exc


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
    except ValueError as exc:
        # Permanent client errors only — re-attempt without response_format
        # if the model rejects that field (common with older OpenAI-compatible
        # endpoints). LLMQuota / Transient / Invalid errors fall through.
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
            raise LLMInvalidResponseError(
                f"Model did not return valid JSON. First 500 chars: {content[:500]}"
            )
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
        raise LLMInvalidResponseError(
            f"Model did not return valid JSON. First 500 chars: {content[:500]}"
        )


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
        raise LLMInvalidResponseError("Model returned empty content")

    usage = data.get("usage", {})
    logger.info(
        "LLM call completed: model=%s elapsed=%.1fs prompt_tokens=%s completion_tokens=%s",
        model, elapsed,
        usage.get("prompt_tokens", "?"),
        usage.get("completion_tokens", "?"),
    )

    return _extract_json(content)


# ─────────────────────────────────────────────────────────────────────────────
# Backoff helpers
# ─────────────────────────────────────────────────────────────────────────────

def _sleep_with_backoff(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    """Sleep for `min(cap, base * 2^attempt) + jitter` seconds.

    Used between transient-error retries within the same model. Jitter avoids
    synchronized thundering-herd across parallel matrix jobs that share a
    free-tier quota.
    """
    delay = min(cap, base * (2 ** attempt))
    delay += random.uniform(0, min(delay * 0.25, 2.0))
    logger.info("Backing off %.1fs before retry (attempt=%d)", delay, attempt)
    time.sleep(delay)


def _sleep_for_quota(retry_after_s: float | None, attempt: int) -> None:
    """Honor server-supplied Retry-After when present, else exponential.

    Floors at 8s because free-tier quotas typically reset on minute boundaries
    and a 1s wait is just going to bounce off 429 again.
    """
    floor = 8.0
    if retry_after_s is not None and retry_after_s > 0:
        delay = max(retry_after_s + random.uniform(0, 2.0), floor)
    else:
        delay = max(min(60.0, 5.0 * (2 ** attempt)) + random.uniform(0, 3.0), floor)
    logger.warning("Quota hit — sleeping %.1fs before next attempt", delay)
    time.sleep(delay)


# ─────────────────────────────────────────────────────────────────────────────
# Per-model attempt loop
# ─────────────────────────────────────────────────────────────────────────────
#
# Per-model budget:
#   • Up to MAX_LENGTH_RETRIES content attempts (force_length on retry).
#   • MAX_QUOTA_HITS quota errors before we stop wasting time and cascade to
#     the next model — quota usually doesn't recover within one daily run.
#   • MAX_TRANSIENT_RETRIES backed-off retries on 5xx / connection errors.
#   • One retry on malformed JSON (might be a transient glitch, never worth
#     more than one extra spin).

MAX_LENGTH_RETRIES = 3
MAX_QUOTA_HITS = 2
MAX_TRANSIENT_RETRIES = 3
MAX_INVALID_JSON_RETRIES = 1


def _try_generate_one(
    model: str,
    manifest: dict,
    settings,
    force_length: bool,
) -> tuple[dict[str, Any], str, int]:
    """One outer attempt: generate, assemble script, count words.

    Internally retries on transient/quota/JSON failures with appropriate
    backoff. Raises LLMQuotaError or LLMTransientError if the per-attempt
    budgets for those classes are exhausted, so the outer caller can decide
    to cascade to the next model.
    """
    quota_hits = 0
    transient_hits = 0
    invalid_json_hits = 0

    while True:
        try:
            payload = _generate_with_model(model, manifest, settings, force_length=force_length)
            script = assemble_script(
                manifest["run_date"],
                payload,
                intro_format=settings.intro_format,
                locale=settings.locale,
            )
            wc = _word_count(script)
            return payload, script, wc

        except LLMQuotaError as exc:
            quota_hits += 1
            if quota_hits > MAX_QUOTA_HITS:
                logger.warning(
                    "Quota budget exhausted for model %s (%d hits) — cascading",
                    model, quota_hits,
                )
                raise
            _sleep_for_quota(exc.retry_after_s, quota_hits)

        except LLMTransientError as exc:
            transient_hits += 1
            if transient_hits > MAX_TRANSIENT_RETRIES:
                logger.warning(
                    "Transient budget exhausted for model %s (%d hits): %s — cascading",
                    model, transient_hits, exc,
                )
                raise
            _sleep_with_backoff(transient_hits)

        except LLMInvalidResponseError as exc:
            invalid_json_hits += 1
            if invalid_json_hits > MAX_INVALID_JSON_RETRIES:
                logger.warning(
                    "Invalid-JSON budget exhausted for model %s — cascading: %s",
                    model, exc,
                )
                # Re-raise as transient so the outer caller treats this as a
                # cascade trigger rather than a hard stop.
                raise LLMTransientError(str(exc)) from exc
            # Brief pause on JSON glitch — usually a sampling artefact.
            time.sleep(2.0)


def _generate_for_model(
    model: str,
    manifest: dict,
    settings,
) -> tuple[dict[str, Any] | None, str | None, int]:
    """Multi-attempt loop for a single model: get the longest script under budget.

    Returns (best_payload, best_script, best_wc). Caller decides whether
    best_wc >= min_script_words is acceptable or it's time to cascade.
    Raises if the model itself is unusable (quota / transient budget).
    """
    best_payload = None
    best_script = None
    best_wc = 0

    last_exc: Exception | None = None

    for attempt in range(MAX_LENGTH_RETRIES):
        force = attempt > 0
        logger.info(
            "Model %s, attempt %d/%d (force_length=%s)",
            model, attempt + 1, MAX_LENGTH_RETRIES, force,
        )
        try:
            payload, script, wc = _try_generate_one(model, manifest, settings, force_length=force)
        except (LLMQuotaError, LLMTransientError) as exc:
            # Per-attempt budget for retryable errors blew up — give up on this model.
            last_exc = exc
            break

        logger.info("Model %s attempt %d produced %d words", model, attempt + 1, wc)

        if wc > best_wc:
            best_payload = payload
            best_script = script
            best_wc = wc

        if wc >= settings.min_script_words:
            return best_payload, best_script, best_wc

        logger.warning(
            "Script too short on model %s: %d words < %d minimum, retrying with force_length",
            model, wc, settings.min_script_words,
        )

    if last_exc is not None and best_wc == 0:
        # Model produced nothing usable AND blew its retryable budget. Surface
        # the underlying class so the cascade caller can log it cleanly.
        raise last_exc

    return best_payload, best_script, best_wc


def generate_episode_script(manifest: dict, local_preview: bool = False, profile: str | None = None) -> EpisodeDraft:
    """Generate the daily/weekly episode script with model cascade and graceful retry.

    Cascade order (configured via env / settings):
        1. settings.llm_editor_model      (LLM_EDITOR_MODEL)
        2. settings.llm_fallback_model    (LLM_FALLBACK_MODEL)   — optional
        3. settings.llm_emergency_model   (LLM_EMERGENCY_MODEL)  — optional

    A model is dropped from cascade as soon as it exhausts its quota or
    transient-retry budget. This is what saves the daily run from the
    2026-04-16 incident: previously a single 429 on Gemini 2.5 Pro burned
    every retry slot in 5 seconds, the misleading 'Script too short: 0 words'
    error was raised, and the FR run cascaded to the same exhausted quota
    on Flash and crashed the same way.

    Raises ValueError if every cascade slot fails. The caller (the daily
    pipeline) will surface that as a workflow-level failure, which is the
    correct outcome — better to skip the day cleanly than ship a broken
    or empty episode.
    """
    settings = load_settings(local_preview=local_preview, profile=profile)

    source_count = manifest.get("source_count", 0)
    if source_count < settings.min_source_count:
        raise ValueError(
            f"Not enough relevant sources: {source_count} < {settings.min_source_count}"
        )

    models: list[str] = [settings.llm_editor_model]
    if settings.llm_fallback_model:
        models.append(settings.llm_fallback_model)
    if settings.llm_emergency_model:
        models.append(settings.llm_emergency_model)
    # De-dup while preserving order in case the caller misconfigures emergency=editor
    seen: set[str] = set()
    cascade = [m for m in models if m and not (m in seen or seen.add(m))]

    errors: list[str] = []
    best_overall_payload: dict[str, Any] | None = None
    best_overall_script: str | None = None
    best_overall_wc = 0
    best_overall_model: str | None = None

    for model in cascade:
        logger.info("Generating script with model: %s (profile=%s)", model, settings.profile_name)
        try:
            payload, script, wc = _generate_for_model(model, manifest, settings)
        except LLMError as exc:
            logger.error("Model %s exhausted retry budget: %s", model, exc)
            errors.append(f"{model}: {exc}")
            continue
        except Exception as exc:
            # Any non-LLM exception (assemble_script validation error, etc.)
            # is permanent — the same prompt won't suddenly produce a valid
            # schema. Skip cascade silently for the model, log loudly.
            logger.error("Model %s failed with permanent error: %s", model, exc)
            errors.append(f"{model}: {exc}")
            continue

        if wc > best_overall_wc:
            best_overall_payload = payload
            best_overall_script = script
            best_overall_wc = wc
            best_overall_model = model

        if wc >= settings.min_script_words and payload is not None and script is not None:
            logger.info(
                "Script generated successfully: %d words, model=%s", wc, model,
            )
            return EpisodeDraft(
                episode_title=payload.get("episode_title", settings.podcast_title),
                episode_summary=payload.get("episode_summary", settings.podcast_description_short),
                opening_news_title=payload.get("opening_news_title", ""),
                script=script,
                tomorrow_concept=payload.get("tomorrow_pedagogical_concept", ""),
                highlights_label=payload.get("highlights_label", "Highlights"),
            )

        # Did produce something, but under the minimum — record and move on
        # to the next model in the cascade. We never silently ship a too-short
        # script, but we DO keep the best draft for the error report so an
        # operator can re-run manually with the partial output if they choose.
        if payload is not None:
            errors.append(
                f"{model}: short script ({wc} < {settings.min_script_words})"
            )

    if best_overall_payload is not None and best_overall_script is not None:
        logger.error(
            "All models exhausted — best draft was %d words from %s "
            "(min %d). Errors: %s",
            best_overall_wc, best_overall_model, settings.min_script_words,
            " | ".join(errors),
        )
    raise ValueError("All editorial generation attempts failed: " + " | ".join(errors))
