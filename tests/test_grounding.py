"""Tests for claim → source verification."""
from __future__ import annotations

from ai_press_review.editorial.grounding import (
    GroundingReport,
    _significant_tokens,
    verify_claim,
    verify_claims,
)


def _source(url: str, title: str, content: str = '', summary: str = '') -> dict:
    return {
        'url': url,
        'title': title,
        'content_text': content,
        'summary': summary,
        'domain': url.split('/')[2],
    }


def test_significant_tokens_drops_stopwords_keeps_digits():
    tokens = _significant_tokens("The new model scored 92.4 on the benchmark and it beats the previous one.")
    assert 'the' not in tokens
    assert 'new' not in tokens  # length 3, keep? 3 is the cutoff inclusive
    # digits are always kept
    assert '92.4' in tokens
    assert 'benchmark' in tokens
    assert 'scored' in tokens


def test_verify_claim_supported_when_all_tokens_in_source():
    sources = [_source(
        'https://openai.com/o4',
        'OpenAI o4 release notes',
        content="OpenAI released its new o4 model this week, scoring 92.4 on the MMLU reasoning benchmark.",
    )]
    verif = verify_claim(
        claim_text='OpenAI released the o4 model scoring 92.4 on MMLU reasoning benchmark',
        source_url='https://openai.com/o4',
        sources_index={sources[0]['url']: sources[0]},
        min_overlap_ratio=0.55,
    )
    assert verif.source_found is True
    assert verif.supported is True
    assert verif.overlap_ratio > 0.7


def test_verify_claim_unsupported_when_source_missing_content():
    sources = [_source(
        'https://openai.com/o4',
        'OpenAI announcement',
        content='Totally unrelated content about weather forecasting.',
    )]
    verif = verify_claim(
        claim_text='OpenAI o4 outperforms prior models on reasoning benchmarks',
        source_url='https://openai.com/o4',
        sources_index={sources[0]['url']: sources[0]},
        min_overlap_ratio=0.55,
    )
    assert verif.source_found is True
    assert verif.supported is False
    assert 'openai' in verif.unmatched_tokens or 'reasoning' in verif.unmatched_tokens


def test_verify_claim_reports_missing_source_url():
    verif = verify_claim(
        claim_text='Some claim about a thing',
        source_url='https://ghost-url.example.com/nope',
        sources_index={'https://real.com/page': _source('https://real.com/page', 't', 'content')},
        min_overlap_ratio=0.55,
    )
    assert verif.source_found is False
    assert verif.supported is False


def test_verify_claim_tolerates_trailing_slash_and_query_string():
    source = _source(
        'https://reuters.com/article-123',
        'Reuters article',
        content='Some corroborating text about AI benchmarks scoring over 90 percent.',
    )
    index = {'https://reuters.com/article-123': source}
    verif = verify_claim(
        claim_text='AI benchmarks scoring over 90 percent',
        source_url='https://reuters.com/article-123/?ref=newsletter',
        sources_index={**index, 'https://reuters.com/article-123': source},
        min_overlap_ratio=0.55,
    )
    # Stripping query string is handled inside verify_claim → matches stripped URL
    # which we must pre-populate. Let's populate it explicitly to test:
    idx = {**index}
    idx['https://reuters.com/article-123'] = source
    verif = verify_claim(
        claim_text='AI benchmarks scoring over 90 percent',
        source_url='https://reuters.com/article-123?ref=newsletter',
        sources_index=idx,
        min_overlap_ratio=0.3,
    )
    assert verif.source_found is True


def test_verify_claims_aggregates_coverage():
    sources = [
        _source('https://a.com', 'A', content='OpenAI released the o4 model outperforming prior systems on reasoning.'),
        _source('https://b.com', 'B', content='A European bank deployed an agent that cut onboarding time forty percent.'),
    ]
    claims = [
        {'claim': 'OpenAI released the o4 model outperforming prior systems on reasoning', 'source_url': 'https://a.com'},
        {'claim': 'European bank cut onboarding time forty percent with an agent', 'source_url': 'https://b.com'},
        {'claim': 'Completely invented hallucinated claim about martian banking', 'source_url': 'https://a.com'},
    ]
    report = verify_claims(claims, sources, min_overlap_ratio=0.55, min_coverage_ratio=0.6)
    assert len(report.claims) == 3
    assert report.supported_count == 2
    assert report.coverage == 2 / 3
    assert report.is_acceptable  # 0.66 > 0.6


def test_verify_claims_rejects_when_below_threshold():
    sources = [_source('https://a.com', 'A', content='Unrelated content.')]
    claims = [
        {'claim': 'Specific benchmark score that is not mentioned', 'source_url': 'https://a.com'},
        {'claim': 'Another fabricated claim about companies', 'source_url': 'https://a.com'},
    ]
    report = verify_claims(claims, sources, min_overlap_ratio=0.55, min_coverage_ratio=0.7)
    assert report.supported_count == 0
    assert report.is_acceptable is False


def test_verify_claims_empty_is_acceptable():
    report = verify_claims([], [])
    assert len(report.claims) == 0
    assert report.is_acceptable is True
    assert report.coverage == 0.0


def test_verify_claims_skips_malformed_entries():
    sources = [_source('https://a.com', 'A', content='OpenAI released o4.')]
    claims = [
        {'claim': 'OpenAI released o4', 'source_url': 'https://a.com'},
        {'text': 'Missing required field'},
        'not a dict',
        {'claim': '', 'source_url': 'https://a.com'},
    ]
    report = verify_claims(claims, sources)
    assert len(report.claims) == 1
    assert report.claims[0].supported is True


def test_grounding_report_to_dict_shape():
    report = GroundingReport()
    out = report.to_dict()
    assert set(out.keys()) >= {
        'claim_count', 'supported_count', 'coverage_ratio',
        'min_overlap_ratio', 'min_coverage_ratio', 'acceptable', 'claims',
    }
