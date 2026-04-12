"""Claim → source verification.

After the LLM generates the script, each claim it emits is checked
against the source manifest: the cited URL must exist, and the claim's
substantive tokens must appear in that source's content_text (lexical
overlap with stopword filtering). This guards against hallucinated
citations and unsupported numerical assertions.

Output: a GroundingReport with per-claim verification status and an
aggregate coverage ratio, which the pipeline can log and — if below a
configurable threshold — surface as a warning or a blocker.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

logger = logging.getLogger(__name__)


# Minimal English stopword list — claims are written in English.
_STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'but', 'by',
    'for', 'from', 'had', 'has', 'have', 'he', 'her', 'his', 'in',
    'into', 'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the',
    'their', 'them', 'they', 'this', 'to', 'was', 'were', 'will',
    'with', 'which', 'who', 'what', 'when', 'where', 'why', 'how',
    'one', 'two', 'three', 'about', 'new', 'also', 'than', 'then',
    'over', 'out', 'up', 'down', 'after', 'before', 'we', 'our',
    'i', 'you', 'your', 'all', 'any', 'just', 'more', 'some',
    'would', 'could', 'should', 'may', 'might', 'can', 'do', 'does',
    'did', 'not', 'no', 'yes', 'very', 'much', 'so', 'if',
}


@dataclass
class ClaimVerification:
    claim: str
    source_url: str
    source_found: bool
    overlap_ratio: float
    supported: bool
    unmatched_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'claim': self.claim,
            'source_url': self.source_url,
            'source_found': self.source_found,
            'overlap_ratio': round(self.overlap_ratio, 3),
            'supported': self.supported,
            'unmatched_tokens': self.unmatched_tokens[:10],
        }


@dataclass
class GroundingReport:
    claims: list[ClaimVerification] = field(default_factory=list)
    min_overlap_ratio: float = 0.55  # threshold for "supported"
    min_coverage_ratio: float = 0.7  # what fraction of claims must be supported

    @property
    def supported_count(self) -> int:
        return sum(1 for c in self.claims if c.supported)

    @property
    def coverage(self) -> float:
        if not self.claims:
            return 0.0
        return self.supported_count / len(self.claims)

    @property
    def is_acceptable(self) -> bool:
        return not self.claims or self.coverage >= self.min_coverage_ratio

    def to_dict(self) -> dict:
        return {
            'claim_count': len(self.claims),
            'supported_count': self.supported_count,
            'coverage_ratio': round(self.coverage, 3),
            'min_overlap_ratio': self.min_overlap_ratio,
            'min_coverage_ratio': self.min_coverage_ratio,
            'acceptable': self.is_acceptable,
            'claims': [c.to_dict() for c in self.claims],
        }


# ── Tokenization ────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+|\d+(?:\.\d+)?")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


def _significant_tokens(text: str) -> set[str]:
    """Lowercased tokens excluding stopwords and very short words, but
    always keeping digit tokens (numbers are the key claim substrate)."""
    tokens: set[str] = set()
    for tok in _tokenize(text):
        if tok in _STOPWORDS:
            continue
        if tok.isdigit():
            tokens.add(tok)
            continue
        if len(tok) < 3:
            continue
        tokens.add(tok)
    return tokens


# ── Verification ────────────────────────────────────────────────────────────

def _sources_index(sources: Iterable[dict]) -> dict[str, dict]:
    """Index sources by URL (and by normalized URL) for fast lookup."""
    index: dict[str, dict] = {}
    for src in sources:
        url = (src.get('url') or '').strip()
        if not url:
            continue
        index[url] = src
        # Also key by URL without trailing slash + without query string to
        # tolerate minor normalization differences between the manifest and
        # the LLM's copy of the URL.
        stripped = url.split('?')[0].rstrip('/')
        index.setdefault(stripped, src)
    return index


def verify_claim(
    claim_text: str,
    source_url: str,
    sources_index: dict[str, dict],
    min_overlap_ratio: float,
) -> ClaimVerification:
    # Source lookup: try both exact and stripped URL.
    normalized = (source_url or '').split('?')[0].rstrip('/')
    source = sources_index.get(source_url) or sources_index.get(normalized)

    claim_tokens = _significant_tokens(claim_text)
    if not claim_tokens:
        return ClaimVerification(
            claim=claim_text, source_url=source_url,
            source_found=source is not None,
            overlap_ratio=0.0, supported=False,
        )

    if source is None:
        return ClaimVerification(
            claim=claim_text, source_url=source_url,
            source_found=False, overlap_ratio=0.0, supported=False,
            unmatched_tokens=sorted(claim_tokens),
        )

    haystack = ' '.join(filter(None, [
        source.get('title', ''),
        source.get('summary', ''),
        source.get('content_text', ''),
    ]))
    source_tokens = _significant_tokens(haystack)

    matched = claim_tokens & source_tokens
    overlap = len(matched) / len(claim_tokens)
    unmatched = sorted(claim_tokens - source_tokens)

    return ClaimVerification(
        claim=claim_text,
        source_url=source_url,
        source_found=True,
        overlap_ratio=overlap,
        supported=overlap >= min_overlap_ratio,
        unmatched_tokens=unmatched,
    )


def verify_claims(
    claims: list[dict],
    sources: list[dict],
    min_overlap_ratio: float = 0.55,
    min_coverage_ratio: float = 0.7,
) -> GroundingReport:
    """Verify every claim against the manifest's sources. Claims missing
    required fields are dropped from the report (not silently treated
    as supported)."""
    index = _sources_index(sources)
    report = GroundingReport(
        min_overlap_ratio=min_overlap_ratio,
        min_coverage_ratio=min_coverage_ratio,
    )
    for raw in claims or []:
        if not isinstance(raw, dict):
            continue
        text = (raw.get('claim') or raw.get('text') or '').strip()
        url = (raw.get('source_url') or raw.get('url') or '').strip()
        if not text or not url:
            continue
        report.claims.append(verify_claim(text, url, index, min_overlap_ratio))

    if report.claims:
        logger.info(
            "Claim grounding: %d/%d supported (%.0f%% coverage, threshold %.0f%%)",
            report.supported_count, len(report.claims),
            report.coverage * 100, report.min_coverage_ratio * 100,
        )
        if not report.is_acceptable:
            unsupported = [c for c in report.claims if not c.supported]
            logger.warning(
                "Claim grounding BELOW threshold. %d unsupported claim(s): %s",
                len(unsupported),
                [f"{c.claim[:80]!r} -> {c.source_url}" for c in unsupported[:3]],
            )
    else:
        logger.info("Claim grounding: no claims emitted by the LLM — skipping verification")

    return report
