"""Generator tests — focus on the 2026-04-16 typed-error + cascade overhaul.

The original failure these tests guard against:

  • Daily pipeline crashed with `ValueError: All editorial generation attempts
    failed: gemini-2.5-pro: Script too short after 4 attempts: 0 words ...`
  • Root cause: HTTP 429 quota exhaustion on the editor model burned all 4
    retry slots in 5 seconds because the old loop used wait_fixed(3) and did
    not branch on status code.
  • The misleading "Script too short: 0 words" message hid the real cause.

The fixes verified here:

  1. Typed exceptions exist and are subclasses of LLMError.
  2. _parse_retry_after honors the HTTP Retry-After header.
  3. _post_chat_completion raises the right typed exception per status code.
  4. The cascade tries multiple models in order and stops on first success.
  5. The cascade falls through on quota errors instead of looping forever.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from ai_press_review.editorial.generator import (
    LLMError,
    LLMInvalidResponseError,
    LLMQuotaError,
    LLMShortScriptError,
    LLMTransientError,
    MAX_LENGTH_RETRIES,
    MAX_QUOTA_HITS,
    MAX_TRANSIENT_RETRIES,
    _parse_retry_after,
    _post_chat_completion,
    _try_generate_one,
    generate_episode_script,
)


# ─── Typed exception hierarchy ───────────────────────────────────────────────

def test_quota_error_is_subclass_of_llm_error():
    assert issubclass(LLMQuotaError, LLMError)


def test_transient_error_is_subclass_of_llm_error():
    assert issubclass(LLMTransientError, LLMError)


def test_invalid_response_error_is_subclass_of_llm_error():
    assert issubclass(LLMInvalidResponseError, LLMError)


def test_short_script_error_is_subclass_of_llm_error():
    assert issubclass(LLMShortScriptError, LLMError)


def test_quota_error_carries_retry_after():
    err = LLMQuotaError("rate limited", retry_after_s=42.0)
    assert err.retry_after_s == 42.0
    assert "rate limited" in str(err)


def test_quota_error_default_retry_after_none():
    err = LLMQuotaError("rate limited")
    assert err.retry_after_s is None


def test_short_script_error_carries_word_count():
    err = LLMShortScriptError("too short", word_count=1492)
    assert err.word_count == 1492


# ─── Retry-After parsing ─────────────────────────────────────────────────────

def _fake_response(status: int, headers: dict | None = None, body: str = ""):
    """Build a minimal requests.Response stand-in for the parsing helpers."""
    fake = SimpleNamespace()
    fake.status_code = status
    fake.headers = headers or {}
    fake.text = body
    fake.json = lambda: {"error": {"message": body}} if body else {}
    return fake


def test_parse_retry_after_returns_seconds_when_present():
    resp = _fake_response(429, {"Retry-After": "30"})
    assert _parse_retry_after(resp) == 30.0


def test_parse_retry_after_lowercase_header_also_works():
    resp = _fake_response(429, {"retry-after": "12.5"})
    assert _parse_retry_after(resp) == 12.5


def test_parse_retry_after_none_when_absent():
    resp = _fake_response(429, {})
    assert _parse_retry_after(resp) is None


def test_parse_retry_after_caps_at_120s():
    # An LLM gateway returning Retry-After: 600 must not block us for 10 min.
    resp = _fake_response(429, {"Retry-After": "600"})
    assert _parse_retry_after(resp) == 120.0


def test_parse_retry_after_returns_none_for_http_date_format():
    # HTTP-date format is rarely sent by LLM APIs and we don't bother parsing.
    resp = _fake_response(429, {"Retry-After": "Wed, 16 Apr 2026 08:00:00 GMT"})
    assert _parse_retry_after(resp) is None


def test_parse_retry_after_returns_none_for_negative_value():
    resp = _fake_response(429, {"Retry-After": "-10"})
    assert _parse_retry_after(resp) is None


# ─── HTTP status → typed exception mapping ───────────────────────────────────

def _settings_stub():
    return SimpleNamespace(
        llm_base_url="https://example.test/v1",
        llm_api_key="dummy",
        llm_timeout_seconds=30,
    )


def test_post_chat_raises_quota_on_429():
    fake = _fake_response(429, {"Retry-After": "20"}, "quota exceeded")
    with patch("ai_press_review.editorial.generator.requests.post", return_value=fake):
        with pytest.raises(LLMQuotaError) as exc_info:
            _post_chat_completion(_settings_stub(), {"model": "x", "messages": []})
    assert exc_info.value.retry_after_s == 20.0


def test_post_chat_raises_transient_on_503():
    fake = _fake_response(503, {}, "service unavailable")
    with patch("ai_press_review.editorial.generator.requests.post", return_value=fake):
        with pytest.raises(LLMTransientError):
            _post_chat_completion(_settings_stub(), {"model": "x", "messages": []})


def test_post_chat_raises_transient_on_500_502_504():
    for status in (500, 502, 504):
        fake = _fake_response(status, {}, f"server error {status}")
        with patch("ai_press_review.editorial.generator.requests.post", return_value=fake):
            with pytest.raises(LLMTransientError):
                _post_chat_completion(_settings_stub(), {"model": "x", "messages": []})


def test_post_chat_raises_value_error_on_400_class():
    # Permanent client errors are NOT retryable — raise plain ValueError so
    # the cascade caller doesn't waste retry budget on them.
    fake = _fake_response(400, {}, "bad request")
    with patch("ai_press_review.editorial.generator.requests.post", return_value=fake):
        with pytest.raises(ValueError) as exc_info:
            _post_chat_completion(_settings_stub(), {"model": "x", "messages": []})
        assert "400" in str(exc_info.value)


def test_post_chat_raises_transient_on_connection_error():
    import requests
    err = requests.ConnectionError("connection refused")
    with patch("ai_press_review.editorial.generator.requests.post", side_effect=err):
        with pytest.raises(LLMTransientError):
            _post_chat_completion(_settings_stub(), {"model": "x", "messages": []})


# ─── Per-model attempt loop budget ───────────────────────────────────────────

def test_try_generate_one_gives_up_after_quota_budget():
    """After MAX_QUOTA_HITS+1 quota errors, the loop bubbles LLMQuotaError up."""
    settings = SimpleNamespace(
        prompt_path=None, llm_temperature=0.2, llm_max_tokens=12000,
        intro_format="daily", locale="en",
    )
    quota_err = LLMQuotaError("rate limited", retry_after_s=0.01)

    with patch(
        "ai_press_review.editorial.generator._generate_with_model",
        side_effect=quota_err,
    ), patch("ai_press_review.editorial.generator._sleep_for_quota"):
        with pytest.raises(LLMQuotaError):
            _try_generate_one("model-x", {"run_date": "2026-04-16"}, settings, force_length=False)


def test_try_generate_one_gives_up_after_transient_budget():
    settings = SimpleNamespace(
        prompt_path=None, llm_temperature=0.2, llm_max_tokens=12000,
        intro_format="daily", locale="en",
    )
    transient_err = LLMTransientError("503 unavailable")

    with patch(
        "ai_press_review.editorial.generator._generate_with_model",
        side_effect=transient_err,
    ), patch("ai_press_review.editorial.generator._sleep_with_backoff"):
        with pytest.raises(LLMTransientError):
            _try_generate_one("model-x", {"run_date": "2026-04-16"}, settings, force_length=False)


# ─── End-to-end cascade ──────────────────────────────────────────────────────
#
# We patch _generate_for_model rather than the deeper helpers because the
# cascade's job is to choose models, not to drive the per-model loop.

def _settings_for_cascade(min_words=2100, fallback="m2", emergency="m3"):
    """Mock the load_settings call from inside generate_episode_script."""
    return SimpleNamespace(
        llm_editor_model="m1",
        llm_fallback_model=fallback,
        llm_emergency_model=emergency,
        min_script_words=min_words,
        min_source_count=1,
        profile_name="daily",
        intro_format="daily",
        locale="en",
        podcast_title="T",
        podcast_description_short="S",
    )


def test_cascade_returns_first_successful_model():
    settings = _settings_for_cascade()
    payload = {
        "episode_title": "ok", "episode_summary": "s",
        "opening_news_title": "o", "tomorrow_pedagogical_concept": "t",
        "highlights_label": "H",
    }
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        return_value=(payload, "script body", 2500),
    ) as mocked:
        draft = generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    assert draft.episode_title == "ok"
    assert draft.script == "script body"
    # Only the first model was tried — no cascade needed.
    assert mocked.call_count == 1
    assert mocked.call_args.args[0] == "m1"


def test_cascade_advances_to_fallback_on_quota():
    settings = _settings_for_cascade()
    payload = {
        "episode_title": "from-fallback", "episode_summary": "s",
        "opening_news_title": "o", "tomorrow_pedagogical_concept": "t",
        "highlights_label": "H",
    }

    def fake_for_model(model, manifest, settings_):
        if model == "m1":
            raise LLMQuotaError("editor quota dead")
        return payload, "fallback script", 2500

    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        side_effect=fake_for_model,
    ) as mocked:
        draft = generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    assert draft.episode_title == "from-fallback"
    assert mocked.call_count == 2
    assert [c.args[0] for c in mocked.call_args_list] == ["m1", "m2"]


def test_cascade_uses_emergency_model_when_fallback_also_fails():
    settings = _settings_for_cascade()
    payload = {
        "episode_title": "from-emergency", "episode_summary": "s",
        "opening_news_title": "o", "tomorrow_pedagogical_concept": "t",
        "highlights_label": "H",
    }

    def fake_for_model(model, manifest, settings_):
        if model in ("m1", "m2"):
            raise LLMQuotaError(f"{model} quota dead")
        return payload, "emergency script", 2500

    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        side_effect=fake_for_model,
    ) as mocked:
        draft = generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    assert draft.episode_title == "from-emergency"
    assert [c.args[0] for c in mocked.call_args_list] == ["m1", "m2", "m3"]


def test_cascade_raises_when_all_models_fail():
    settings = _settings_for_cascade()
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        side_effect=LLMQuotaError("dead"),
    ):
        with pytest.raises(ValueError) as exc_info:
            generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    msg = str(exc_info.value)
    assert "All editorial generation attempts failed" in msg
    # Each model surface should appear in the diagnostic chain.
    for model in ("m1", "m2", "m3"):
        assert model in msg


def test_cascade_does_not_silently_ship_short_script():
    """If every model produces a script under min_script_words, raise."""
    settings = _settings_for_cascade(min_words=2100)
    payload = {
        "episode_title": "short", "episode_summary": "s",
        "opening_news_title": "o", "tomorrow_pedagogical_concept": "t",
        "highlights_label": "H",
    }
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        return_value=(payload, "tiny", 500),
    ):
        with pytest.raises(ValueError) as exc_info:
            generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    msg = str(exc_info.value)
    assert "short script" in msg


def test_cascade_skips_unset_emergency_model():
    settings = _settings_for_cascade(emergency="")
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        side_effect=LLMQuotaError("dead"),
    ) as mocked:
        with pytest.raises(ValueError):
            generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    # Only m1 and m2 — no emergency tier configured.
    assert [c.args[0] for c in mocked.call_args_list] == ["m1", "m2"]


def test_cascade_dedups_duplicated_model_names():
    """If the operator misconfigures fallback=editor or emergency=fallback,
    the cascade must not call the same model twice in a row."""
    settings = SimpleNamespace(
        llm_editor_model="m1",
        llm_fallback_model="m1",  # accidental duplicate
        llm_emergency_model="m2",
        min_script_words=2100,
        min_source_count=1,
        profile_name="daily",
        intro_format="daily",
        locale="en",
        podcast_title="T",
        podcast_description_short="S",
    )
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
        side_effect=LLMQuotaError("dead"),
    ) as mocked:
        with pytest.raises(ValueError):
            generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    # m1 only once, then m2 — no duplicate m1 call.
    assert [c.args[0] for c in mocked.call_args_list] == ["m1", "m2"]


def test_cascade_aborts_early_on_insufficient_sources():
    settings = _settings_for_cascade()
    settings.min_source_count = 10
    with patch(
        "ai_press_review.editorial.generator.load_settings",
        return_value=settings,
    ), patch(
        "ai_press_review.editorial.generator._generate_for_model",
    ) as mocked:
        with pytest.raises(ValueError) as exc_info:
            generate_episode_script({"source_count": 5, "run_date": "2026-04-16"})

    assert "Not enough relevant sources" in str(exc_info.value)
    # Generator was never invoked — we bailed at the precondition check.
    assert mocked.call_count == 0


# ─── Sanity check on the budget constants (regression guard) ─────────────────

def test_per_model_budgets_have_sane_defaults():
    # The 2026-04-16 incident burned 4 attempts in 5 seconds. New defaults
    # should:
    #   - Allow length retries (force_length kicks in when too short)
    #   - Cap quota hits well below "infinity"
    #   - Allow at least 2 transient retries (5xx flakiness is common)
    assert MAX_LENGTH_RETRIES >= 2
    assert MAX_LENGTH_RETRIES <= 5
    assert MAX_QUOTA_HITS >= 1
    assert MAX_QUOTA_HITS <= 3
    assert MAX_TRANSIENT_RETRIES >= 2
    assert MAX_TRANSIENT_RETRIES <= 5
