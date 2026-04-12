"""Tests for the multi-pass editorial scaffolding."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

from ai_press_review.editorial.passes import (
    _cacheable,
    build_ledger_messages,
    build_writer_messages,
    run_ledger_pass,
)


class _FakeSettings:
    """Minimal settings stub used by build_*_messages."""
    def __init__(self, tmp_path):
        prompt = tmp_path / 'prompt.txt'
        prompt.write_text('You are a host.', encoding='utf-8')
        self.prompt_path = prompt
        self.llm_editor_model = 'editor-model'
        self.llm_ledger_model = 'ledger-model'
        self.llm_max_tokens = 4000
        self.podcast_title = 'AI Press Review'
        self.podcast_subtitle = '40 sources. 15 minutes.'
        self.target_duration_min = 14
        self.target_duration_max = 18
        self.min_script_words = 2500


def test_cacheable_wraps_content_as_openai_compatible_cache_part():
    parts = _cacheable('hello')
    assert isinstance(parts, list)
    assert parts[0]['type'] == 'text'
    assert parts[0]['text'] == 'hello'
    assert parts[0]['cache_control'] == {'type': 'ephemeral'}


def test_build_ledger_messages_with_cache(tmp_path):
    settings = _FakeSettings(tmp_path)
    manifest = {
        'run_date': '2026-04-12',
        'sources': [
            {'url': 'https://a.com', 'title': 'A', 'domain': 'a.com',
             'summary': 's', 'content_text': 'c', 'relevance_score': 5.0},
        ],
    }
    msgs = build_ledger_messages(manifest, settings, enable_cache=True)
    assert len(msgs) == 2
    assert msgs[0]['role'] == 'system'
    assert msgs[1]['role'] == 'user'
    # Each content is a list with cache_control.
    assert msgs[0]['content'][0]['cache_control'] == {'type': 'ephemeral'}
    assert msgs[1]['content'][0]['cache_control'] == {'type': 'ephemeral'}
    # User content references the sole source URL.
    assert 'https://a.com' in msgs[1]['content'][0]['text']


def test_build_ledger_messages_without_cache(tmp_path):
    settings = _FakeSettings(tmp_path)
    manifest = {'run_date': '2026-04-12', 'sources': []}
    msgs = build_ledger_messages(manifest, settings, enable_cache=False)
    assert isinstance(msgs[0]['content'], str)
    assert isinstance(msgs[1]['content'], str)


def test_build_writer_messages_filters_to_cited_sources(tmp_path):
    settings = _FakeSettings(tmp_path)
    manifest = {
        'sources': [
            {'url': 'https://a.com', 'title': 'A', 'content_text': 'A content'},
            {'url': 'https://b.com', 'title': 'B', 'content_text': 'B content'},
            {'url': 'https://c.com', 'title': 'C', 'content_text': 'C content'},
        ],
    }
    ledger = {
        'stories': [
            {'pillar': 'ai_news', 'headline': 'h', 'source_urls': ['https://a.com', 'https://c.com']},
        ],
    }
    msgs = build_writer_messages(
        ledger, manifest, settings,
        writer_schema={'x': 'y'},
        length_instructions='write at least N words',
        enable_cache=False,
    )
    # The stable context block should contain the cited sources only.
    combined = msgs[1]['content']
    assert 'A content' in combined
    assert 'C content' in combined
    assert 'B content' not in combined


def test_run_ledger_pass_records_metric_and_returns_parsed(tmp_path, monkeypatch):
    """Happy path: parses JSON response and records metric."""
    import ai_press_review.editorial.passes as passes_mod
    recorded = []
    monkeypatch.setattr(passes_mod, 'record_llm_call', lambda **kw: recorded.append(kw))

    settings = _FakeSettings(tmp_path)
    manifest = {'run_date': '2026-04-12', 'sources': []}

    fake_response = {
        'choices': [{'message': {'content': json.dumps({'stories': [{'pillar': 'ai_news'}]})}}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 200},
    }
    post = MagicMock(return_value=fake_response)
    extract_content = lambda data: data['choices'][0]['message']['content']
    extract_json = lambda s: json.loads(s)

    ledger = run_ledger_pass(
        manifest, settings,
        post_chat_completion=post,
        extract_message_content=extract_content,
        extract_json=extract_json,
        enable_cache=True,
    )
    assert ledger == {'stories': [{'pillar': 'ai_news'}]}
    assert len(recorded) == 1
    assert recorded[0]['phase'] == 'ledger'
    assert recorded[0]['success'] is True
    assert recorded[0]['prompt_tokens'] == 100


def test_run_ledger_pass_records_failure_on_exception(tmp_path, monkeypatch):
    import ai_press_review.editorial.passes as passes_mod
    recorded = []
    monkeypatch.setattr(passes_mod, 'record_llm_call', lambda **kw: recorded.append(kw))

    settings = _FakeSettings(tmp_path)
    manifest = {'run_date': '2026-04-12', 'sources': []}

    def _raise(*args, **kwargs):
        raise RuntimeError('upstream dead')

    try:
        run_ledger_pass(
            manifest, settings,
            post_chat_completion=_raise,
            extract_message_content=lambda d: '',
            extract_json=lambda s: {},
        )
        assert False, 'should have raised'
    except RuntimeError:
        pass

    assert len(recorded) == 1
    assert recorded[0]['success'] is False
