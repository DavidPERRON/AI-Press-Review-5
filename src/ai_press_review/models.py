from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceItem:
    url: str
    title: str
    domain: str
    published_at: str | None = None
    summary: str | None = None
    content_text: str | None = None
    relevance_score: float = 0.0
    queries: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeDraft:
    episode_title: str
    episode_summary: str
    opening_news_title: str
    script: str
    tomorrow_concept: str
    highlights_label: str
    key_claims: list[dict[str, Any]] = field(default_factory=list)
    grounding_report: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishedEpisode:
    date: str
    title: str
    slug: str
    summary: str
    audio_url: str
    audio_bytes: int
    duration_seconds: int | None
    source_manifest_url: str
    published_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
