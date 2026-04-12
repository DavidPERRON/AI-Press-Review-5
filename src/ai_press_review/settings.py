from __future__ import annotations

import os
from dataclasses import dataclass
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
    llm_timeout_seconds: int
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

    @property
    def prompt_path(self) -> Path:
        return CONFIG_DIR / 'prompt_system.txt'


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


def load_settings(local_preview: bool = False) -> Settings:
    config = _yaml_config()

    local_base = _env('LOCAL_LLM_BASE_URL') if local_preview else ''
    llm_base_default = local_base or _env('LLM_BASE_URL')

    local_model = _env('LOCAL_LLM_EDITOR_MODEL') if local_preview else ''
    llm_model_default = local_model or _env('LLM_EDITOR_MODEL')

    return Settings(
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
        llm_timeout_seconds=int(_env('LLM_TIMEOUT_SECONDS', '180')),
        cartesia_api_key=_env('CARTESIA_API_KEY'),
        cartesia_voice_id=_env('CARTESIA_VOICE_ID'),
        cartesia_model_id=_env('CARTESIA_MODEL_ID', 'sonic-3'),
        cartesia_version=_env('CARTESIA_VERSION', '2025-04-16'),
        cartesia_language=_env('CARTESIA_LANGUAGE', 'en'),
        cartesia_speed=float(_env('CARTESIA_SPEED', '1.0')),
        cartesia_volume=float(_env('CARTESIA_VOLUME', '1.0')),
        cartesia_emotion=_env('CARTESIA_EMOTION', 'neutral'),
        r2_bucket_name=_env('R2_BUCKET_NAME', 'pressreview'),
        r2_endpoint=_env('R2_ENDPOINT'),
        r2_access_key_id=_env('R2_ACCESS_KEY_ID'),
        r2_secret_access_key=_env('R2_SECRET_ACCESS_KEY'),
        r2_region=_env('R2_REGION', 'auto'),
        r2_audio_prefix=_env('R2_AUDIO_PREFIX', 'episodes/'),
        newsapi_api_key=_env('NEWSAPI_API_KEY'),
        newsapi_query=_env('NEWSAPI_QUERY', 'artificial intelligence OR generative AI OR large language model OR AI banking OR AI finance'),
        newsapi_page_size=int(_env('NEWSAPI_PAGE_SIZE', '50')),
    )


def load_sources_config() -> dict:
    with (CONFIG_DIR / 'sources.yaml').open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}
