from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / 'config'
DATA_DIR = ROOT / 'data'
DOCS_DIR = ROOT / 'docs'

load_dotenv(ROOT / '.env', override=False)


@dataclass
class ScoringConfig:
    min_relevance: float = 3.0
    min_text_length: int = 180
    similarity_threshold: float = 0.88
    max_per_domain: int = 25
    banned_terms: list[str] = field(default_factory=list)
    ai_terms_high: list[str] = field(default_factory=list)
    ai_terms_mid: list[str] = field(default_factory=list)
    ai_terms_low: list[str] = field(default_factory=list)
    signal_words_strong: list[str] = field(default_factory=list)
    signal_words_medium: list[str] = field(default_factory=list)
    domain_authority: dict[str, float] = field(default_factory=dict)


@dataclass
class Settings:
    podcast_title: str
    podcast_subtitle: str
    podcast_author: str
    podcast_email: str
    podcast_language: str
    podcast_description_short: str
    podcast_description_long: str
    category_primary: str
    category_secondary: str
    explicit: bool
    cover_image_path: str
    site_base_url: str
    rss_feed_url: str
    public_audio_base_url: str
    target_duration_min: int
    target_duration_max: int
    min_script_words: int
    min_source_count: int
    freshness_hours: int
    exclude_previous_episode: bool
    retention_days: int
    timezone: str
    publish_hour_local: int
    weekdays_only: bool
    llm_base_url: str
    llm_api_key: str
    llm_editor_model: str
    llm_fallback_model: str
    llm_ledger_model: str
    llm_timeout_seconds: int
    llm_max_tokens: int
    llm_temperature: float
    llm_enable_prompt_cache: bool
    editorial_mode: str  # 'single_pass' | 'multi_pass'
    grounding_min_overlap: float
    grounding_min_coverage: float
    tts_chunk_max_chars: int
    cartesia_api_key: str
    cartesia_voice_id: str
    cartesia_model_id: str
    cartesia_version: str
    cartesia_language: str
    cartesia_speed: float
    cartesia_volume: float
    cartesia_emotion: str
    r2_bucket_name: str
    r2_endpoint: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_region: str
    r2_audio_prefix: str
    newsapi_api_key: str
    newsapi_query: str
    newsapi_page_size: int
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    # Profile fields
    profile_name: str = 'daily'
    prefer_unused: bool = False
    unused_score_bonus: float = 0.0
    reuse_min_score: float = 0.0
    intro_format: str = 'daily'
    prompt_file: str = 'prompt_system.txt'

    @property
    def prompt_path(self) -> Path:
        return CONFIG_DIR / self.prompt_file


def _yaml_config() -> dict[str, Any]:
    with (CONFIG_DIR / 'podcast.yaml').open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}


def _yaml_get(config: dict[str, Any], path: str, default: Any = '') -> Any:
    current: Any = config
    for part in path.split('.'):
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
    return current if current is not None else default


def _env(name: str, default: str = '') -> str:
    value = os.getenv(name)
    if value is None:
        value = default
    return str(value).strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _load_scoring(config: dict[str, Any]) -> ScoringConfig:
    s = config.get('scoring', {}) or {}
    return ScoringConfig(
        min_relevance=float(s.get('min_relevance', 3.0)),
        min_text_length=int(s.get('min_text_length', 180)),
        similarity_threshold=float(s.get('similarity_threshold', 0.88)),
        max_per_domain=int(s.get('max_per_domain', 25)),
        banned_terms=list(s.get('banned_terms', [])),
        ai_terms_high=list(s.get('ai_terms_high', [])),
        ai_terms_mid=list(s.get('ai_terms_mid', [])),
        ai_terms_low=list(s.get('ai_terms_low', [])),
        signal_words_strong=list(s.get('signal_words_strong', [])),
        signal_words_medium=list(s.get('signal_words_medium', [])),
        domain_authority=dict(s.get('domain_authority', {})),
    )


def _apply_profile(settings: Settings, config: dict[str, Any], profile: str) -> None:
    profiles = config.get('profiles', {}) or {}
    prof = profiles.get(profile)
    if not prof:
        return
    settings.profile_name = profile
    if 'freshness_hours' in prof:
        settings.freshness_hours = int(prof['freshness_hours'])
    if 'exclude_previous_episode' in prof:
        settings.exclude_previous_episode = bool(prof['exclude_previous_episode'])
    if 'min_source_count' in prof:
        settings.min_source_count = int(prof['min_source_count'])
    if 'min_script_words' in prof:
        settings.min_script_words = int(prof['min_script_words'])
    if 'target_duration_min' in prof:
        settings.target_duration_min = int(prof['target_duration_min'])
    if 'target_duration_max' in prof:
        settings.target_duration_max = int(prof['target_duration_max'])
    if 'prompt_file' in prof:
        settings.prompt_file = str(prof['prompt_file'])
    if 'intro_format' in prof:
        settings.intro_format = str(prof['intro_format'])
    if 'prefer_unused' in prof:
        settings.prefer_unused = bool(prof['prefer_unused'])
    if 'unused_score_bonus' in prof:
        settings.unused_score_bonus = float(prof['unused_score_bonus'])
    if 'reuse_min_score' in prof:
        settings.reuse_min_score = float(prof['reuse_min_score'])


def load_settings(local_preview: bool = False, profile: str | None = None) -> Settings:
    config = _yaml_config()

    local_base = _env('LOCAL_LLM_BASE_URL') if local_preview else ''
    llm_base_default = local_base or _env('LLM_BASE_URL')

    local_model = _env('LOCAL_LLM_EDITOR_MODEL') if local_preview else ''
    llm_model_default = local_model or _env('LLM_EDITOR_MODEL')

    settings = Settings(
        podcast_title=_env('PODCAST_TITLE', _yaml_get(config, 'title', 'AI Press Review')),
        podcast_subtitle=_env('PODCAST_SUBTITLE', _yaml_get(config, 'subtitle', '')),
        podcast_author=_env('PODCAST_AUTHOR', _yaml_get(config, 'author', '')),
        podcast_email=_env('PODCAST_EMAIL', _yaml_get(config, 'email', '')),
        podcast_language=_env('PODCAST_LANGUAGE', _yaml_get(config, 'language', 'en')),
        podcast_description_short=_env('PODCAST_DESCRIPTION_SHORT', _yaml_get(config, 'short_description', '')),
        podcast_description_long=_env('PODCAST_DESCRIPTION_LONG', _yaml_get(config, 'long_description', '')),
        category_primary=_env('PODCAST_CATEGORY_PRIMARY', _yaml_get(config, 'category_primary', 'Business')),
        category_secondary=_env('PODCAST_CATEGORY_SECONDARY', _yaml_get(config, 'category_secondary', '')),
        explicit=_env_bool('PODCAST_EXPLICIT', bool(_yaml_get(config, 'explicit', False))),
        cover_image_path=_env('PODCAST_COVER_IMAGE', _yaml_get(config, 'cover_image', 'assets/podcast-cover.png')),
        site_base_url=_env('SITE_BASE_URL', _yaml_get(config, 'site_url', '')),
        rss_feed_url=_env('RSS_FEED_URL', _yaml_get(config, 'feed_url', '')),
        public_audio_base_url=_env('PUBLIC_AUDIO_BASE_URL', _yaml_get(config, 'public_audio_base_url', '')),
        target_duration_min=int(_env('TARGET_DURATION_MIN', str(_yaml_get(config, 'editorial.target_duration_min', 14)))),
        target_duration_max=int(_env('TARGET_DURATION_MAX', str(_yaml_get(config, 'editorial.target_duration_max', 18)))),
        min_script_words=int(_env('MIN_SCRIPT_WORDS', str(_yaml_get(config, 'editorial.min_script_words', 2500)))),
        min_source_count=int(_env('MIN_SOURCE_COUNT', str(_yaml_get(config, 'editorial.min_source_count', 45)))),
        freshness_hours=int(_env('FRESHNESS_HOURS', str(_yaml_get(config, 'editorial.freshness_hours', 48)))),
        exclude_previous_episode=_env_bool('EXCLUDE_PREVIOUS_EPISODE', bool(_yaml_get(config, 'editorial.exclude_previous_episode', True))),
        retention_days=int(_env('RETENTION_DAYS', str(_yaml_get(config, 'retention_days', 10)))),
        timezone=_env('PUBLISH_TIMEZONE', _yaml_get(config, 'publish_timezone', 'Europe/Paris')),
        publish_hour_local=int(_env('PUBLISH_HOUR_LOCAL', str(_yaml_get(config, 'schedule.publish_hour_local', 7)))),
        weekdays_only=_env_bool('WEEKDAYS_ONLY', bool(_yaml_get(config, 'schedule.weekdays_only', True))),
        llm_base_url=llm_base_default,
        llm_api_key=_env('LLM_API_KEY', 'unused' if local_preview else ''),
        llm_editor_model=llm_model_default,
        llm_fallback_model=_env('LLM_FALLBACK_MODEL'),
        llm_ledger_model=_env('LLM_LEDGER_MODEL', _yaml_get(config, 'llm.ledger_model', '')),
        llm_timeout_seconds=int(_env('LLM_TIMEOUT_SECONDS', str(_yaml_get(config, 'llm.timeout_seconds', 180)))),
        llm_max_tokens=int(_yaml_get(config, 'llm.max_tokens', 12000)),
        llm_temperature=float(_yaml_get(config, 'llm.temperature', 0.2)),
        llm_enable_prompt_cache=_env_bool('LLM_ENABLE_PROMPT_CACHE', bool(_yaml_get(config, 'llm.enable_prompt_cache', True))),
        editorial_mode=_env('EDITORIAL_MODE', _yaml_get(config, 'editorial.mode', 'single_pass')),
        grounding_min_overlap=float(_env('GROUNDING_MIN_OVERLAP', str(_yaml_get(config, 'editorial.grounding_min_overlap', 0.55)))),
        grounding_min_coverage=float(_env('GROUNDING_MIN_COVERAGE', str(_yaml_get(config, 'editorial.grounding_min_coverage', 0.7)))),
        tts_chunk_max_chars=int(_yaml_get(config, 'tts.chunk_max_chars', 1800)),
        cartesia_api_key=_env('CARTESIA_API_KEY'),
        cartesia_voice_id=_env('CARTESIA_VOICE_ID'),
        cartesia_model_id=_env('CARTESIA_MODEL_ID', 'sonic-3'),
        cartesia_version=_env('CARTESIA_VERSION', '2025-04-16'),
        cartesia_language=_env('CARTESIA_LANGUAGE', 'en'),
        cartesia_speed=float(_env('CARTESIA_SPEED', str(_yaml_get(config, 'tts.speed', 1.0)))),
        cartesia_volume=float(_env('CARTESIA_VOLUME', str(_yaml_get(config, 'tts.volume', 1.0)))),
        cartesia_emotion=_env('CARTESIA_EMOTION', str(_yaml_get(config, 'tts.emotion', 'neutral'))),
        r2_bucket_name=_env('R2_BUCKET_NAME', 'pressreview'),
        r2_endpoint=_env('R2_ENDPOINT'),
        r2_access_key_id=_env('R2_ACCESS_KEY_ID'),
        r2_secret_access_key=_env('R2_SECRET_ACCESS_KEY'),
        r2_region=_env('R2_REGION', 'auto'),
        r2_audio_prefix=_env('R2_AUDIO_PREFIX', 'episodes/'),
        newsapi_api_key=_env('NEWSAPI_API_KEY'),
        newsapi_query=_env('NEWSAPI_QUERY', 'artificial intelligence OR generative AI OR large language model OR AI banking OR AI finance'),
        newsapi_page_size=int(_env('NEWSAPI_PAGE_SIZE', '50')),
        scoring=_load_scoring(config),
    )

    if profile:
        _apply_profile(settings, config, profile)

    return settings


def load_sources_config() -> dict:
    with (CONFIG_DIR / 'sources.yaml').open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}
