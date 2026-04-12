"""Multi-pass editorial pipeline.

Problem with single-shot prompting: the LLM must simultaneously parse
40+ raw articles, prioritize stories, and write a polished 3000-word
script. The model takes shortcuts — it recycles formulaic bridges,
drops less obvious connections, and occasionally blurs which source
backs which claim.

Multi-pass decomposes the task:

1. **Ledger pass** (cheap model) — reads the manifest, emits a
   structured JSON ledger of N stories, each with key facts, scale,
   and source URLs. This becomes the "running order" the writer
   consumes.
2. **Writer pass** (premium model) — receives the ledger plus the
   full text of only the cited sources, and writes the script.
   Much smaller context, higher signal density.

Benefits:
- The ledger pass acts as a forced-explanation step: the model can't
  hallucinate a topic that is not in the manifest, because it had to
  extract it structurally first.
- Better prompt caching hit rate: the system prompt (~2KB) + ledger
  (~3KB) is stable across writer retries, only the "you were too
  short" addendum changes.
- Cleaner division of labour: use a cheap model for extraction
  (e.g. Haiku) and a premium model for writing (e.g. Opus).

Activation: controlled by `settings.editorial_mode` ("single_pass" or
"multi_pass"). Default single_pass to preserve the existing workflow
until operator has validated quality on a few runs.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from ..observability import record_llm_call

logger = logging.getLogger(__name__)


LEDGER_SCHEMA = {
    "stories": [
        {
            "pillar": "one of: ai_news | use_cases_and_deployments | tools_and_practice | weak_signals_and_trends | research_and_breakthroughs | education_and_pedagogy",
            "headline": "string — one-sentence summary of the story",
            "key_facts": [
                "array of 2-5 concrete facts from the sources: numbers, company names, product names, benchmark scores, dates, deployment scales. Each fact MUST be traceable to a source.",
            ],
            "why_it_matters": "one sentence — the 'so what' for a busy professional",
            "source_urls": [
                "array of source URLs that substantiate this story. Copy verbatim from the manifest.",
            ],
            "confidence": "high | medium | low — 'low' means single-source or speculative, used to route into weak_signals",
        }
    ],
    "themes_of_day": [
        "2-4 one-line threads connecting multiple stories — cross-cutting observations",
    ],
}


LEDGER_INSTRUCTIONS = (
    "You are the research analyst for a daily AI press review. Read the source manifest "
    "and extract a STRUCTURED LEDGER of the day's stories. Do NOT write prose. Do NOT "
    "summarize broadly. Your only job: list discrete, verifiable stories with their "
    "key facts and source URLs.\n\n"
    "Rules:\n"
    "- Each story MUST have at least one concrete number, name, or deliverable.\n"
    "- Each story MUST cite at least one source URL from the manifest.\n"
    "- Single-source stories go into pillar 'weak_signals_and_trends' with confidence='low'.\n"
    "- Cluster sources that report the same story into ONE story entry with multiple source_urls.\n"
    "- Skip anything that is regulatory speculation, rumor, or opinion.\n"
    "- Target 12-18 stories total across all pillars.\n"
    "Return JSON only, matching the schema provided."
)


def _cacheable(content: str) -> list[dict[str, Any]]:
    """Wrap a long text block as a cacheable content part.

    OpenAI-compatible gateways (OpenRouter, Anthropic, LiteLLM) honor
    `cache_control` on message content parts. On gateways that ignore
    it, the content is simply delivered as plain text.
    """
    return [
        {
            "type": "text",
            "text": content,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def build_ledger_messages(
    manifest: dict,
    settings,
    enable_cache: bool = True,
) -> list[dict[str, Any]]:
    system = (
        "You extract a structured JSON ledger from a news manifest. "
        "Return JSON only — no markdown, no prose. "
        "Schema:\n" + json.dumps(LEDGER_SCHEMA, indent=2)
    )

    # Compact manifest for the ledger pass: keep only title, url, summary,
    # short content, and score. The full text is only needed by the writer.
    compact_sources = [
        {
            'url': s.get('url'),
            'title': s.get('title'),
            'domain': s.get('domain'),
            'summary': (s.get('summary') or '')[:400],
            'content_text': (s.get('content_text') or '')[:800],
            'relevance_score': s.get('relevance_score'),
        }
        for s in manifest.get('sources', [])
    ]

    # Cluster hints (if the collector produced them) — helps the ledger
    # pass group sources correctly.
    cluster_hint = ''
    if manifest.get('clusters'):
        cluster_hint = (
            "\n\nCLUSTER HINTS (sources that were grouped pre-LLM as reporting the same story):\n"
            + json.dumps(manifest['clusters'][:20], indent=2)
        )

    user_text = (
        LEDGER_INSTRUCTIONS
        + "\n\n=== SOURCE MANIFEST ===\n"
        + json.dumps(compact_sources, ensure_ascii=False)
        + cluster_hint
    )

    if enable_cache:
        return [
            {"role": "system", "content": _cacheable(system)},
            {"role": "user", "content": _cacheable(user_text)},
        ]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


def build_writer_messages(
    ledger: dict,
    manifest: dict,
    settings,
    writer_schema: dict,
    length_instructions: str,
    enable_cache: bool = True,
) -> list[dict[str, Any]]:
    """Writer pass: receives the compact ledger + the full content of
    only the sources cited in the ledger."""
    cited_urls: set[str] = set()
    for story in ledger.get('stories', []):
        for url in story.get('source_urls', []):
            if url:
                cited_urls.add(url)

    cited_sources = [s for s in manifest.get('sources', []) if s.get('url') in cited_urls]

    system_text = settings.prompt_path.read_text(encoding='utf-8')

    stable_context = (
        "=== DAILY STORY LEDGER (produced by the research pass) ===\n"
        + json.dumps(ledger, ensure_ascii=False, indent=2)
        + "\n\n=== FULL TEXT OF CITED SOURCES ===\n"
        + json.dumps([
            {
                'url': s.get('url'),
                'title': s.get('title'),
                'domain': s.get('domain'),
                'content_text': (s.get('content_text') or '')[:2200],
            }
            for s in cited_sources
        ], ensure_ascii=False)
    )

    constraints = {
        'title': settings.podcast_title,
        'subtitle': settings.podcast_subtitle,
        'target_duration_min': settings.target_duration_min,
        'target_duration_max': settings.target_duration_max,
        'minimum_script_words': settings.min_script_words,
        'required_output': writer_schema,
    }
    writer_task = (
        "Write today's script from the ledger above. Use the cited sources for concrete "
        "details (numbers, names, quotes) but do NOT introduce facts absent from the ledger "
        "or sources. Follow all style rules in the system prompt.\n\n"
        + json.dumps({'constraints': constraints, 'instructions': length_instructions}, ensure_ascii=False)
    )

    if enable_cache:
        return [
            {"role": "system", "content": _cacheable(system_text)},
            {"role": "user", "content": _cacheable(stable_context)},
            {"role": "user", "content": writer_task},
        ]
    return [
        {"role": "system", "content": system_text},
        {"role": "user", "content": stable_context + "\n\n" + writer_task},
    ]


def run_ledger_pass(
    manifest: dict,
    settings,
    post_chat_completion,
    extract_message_content,
    extract_json,
    enable_cache: bool = True,
) -> dict:
    """Execute the research/ledger pass. Returns the parsed ledger dict.

    `post_chat_completion`, `extract_message_content`, `extract_json`
    are injected from generator.py to avoid a circular import.
    """
    model = (settings.llm_ledger_model or settings.llm_editor_model).strip()
    messages = build_ledger_messages(manifest, settings, enable_cache=enable_cache)

    payload = {
        'model': model,
        'temperature': 0.1,
        'messages': messages,
        'max_tokens': min(settings.llm_max_tokens, 4000),
        'response_format': {'type': 'json_object'},
    }

    start = time.monotonic()
    usage: dict[str, Any] = {}
    success = False
    try:
        try:
            data = post_chat_completion(settings, payload)
        except Exception as exc:
            msg = str(exc).lower()
            if 'json_object' in msg or 'response format' in msg or '405' in msg:
                payload.pop('response_format', None)
                data = post_chat_completion(settings, payload)
            else:
                raise

        content = extract_message_content(data)
        if not content.strip():
            raise ValueError("Ledger pass returned empty content")

        usage = data.get('usage', {}) or {}
        ledger = extract_json(content)
        success = True
        logger.info(
            "Ledger pass: %d stories extracted (model=%s, %.1fs)",
            len(ledger.get('stories', [])),
            model,
            time.monotonic() - start,
        )
        return ledger
    finally:
        elapsed = time.monotonic() - start
        cached = (
            usage.get('cache_read_input_tokens')
            or usage.get('prompt_tokens_details', {}).get('cached_tokens')
            or 0
        )
        record_llm_call(
            run_date=manifest.get('run_date', 'unknown'),
            model=model,
            prompt_tokens=int(usage.get('prompt_tokens') or 0),
            completion_tokens=int(usage.get('completion_tokens') or 0),
            cached_tokens=int(cached or 0),
            duration_s=elapsed,
            phase='ledger',
            success=success,
        )
