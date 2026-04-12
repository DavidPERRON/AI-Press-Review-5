from __future__ import annotations

import logging
import time
from pathlib import Path

from .collect import collect_sources
from .editorial.generator import generate_episode_script
from .models import PublishedEpisode
from .publish.feed import publish_episode
from .settings import load_settings
from .storage.r2 import upload_file
from .tts.cartesia import synthesize_script
from .utils import fingerprint, iso_now, safe_slug, write_json

logger = logging.getLogger(__name__)


def run_pipeline(
    run_date: str,
    local_preview: bool = False,
    render_audio: bool = True,
    upload_audio: bool = False,
    publish_feed: bool = False,
) -> dict:
    pipeline_start = time.monotonic()
    settings = load_settings(local_preview=local_preview)
    logger.info("Pipeline started: date=%s preview=%s", run_date, local_preview)

    # Phase 1: Collect
    t0 = time.monotonic()
    manifest = collect_sources(run_date=run_date, local_preview=local_preview)
    logger.info("Collection completed: %d sources in %.1fs", manifest['source_count'], time.monotonic() - t0)

    # Phase 2: Generate editorial script
    t0 = time.monotonic()
    draft = generate_episode_script(manifest, local_preview=local_preview)
    logger.info("Editorial completed: %d words in %.1fs", len(draft.script.split()), time.monotonic() - t0)

    outputs_dir = Path('output') / run_date
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / 'script.txt').write_text(draft.script, encoding='utf-8')
    (outputs_dir / 'episode_summary.txt').write_text(draft.episode_summary, encoding='utf-8')

    result = {
        'run_date': run_date,
        'source_count': manifest['source_count'],
        'script_title': draft.episode_title,
        'script_words': len(draft.script.split()),
        'rendered_audio': False,
        'uploaded_audio': False,
        'published': False,
    }

    audio_name = f"{run_date}-{safe_slug(draft.episode_title)}.mp3"
    audio_path = outputs_dir / audio_name
    audio_meta = None

    # Phase 3: TTS
    if render_audio:
        t0 = time.monotonic()
        audio_meta = synthesize_script(draft.script, audio_path, local_preview=local_preview)
        logger.info(
            "TTS completed: %d chunks, %ds duration, %.1f MB in %.1fs",
            audio_meta['chunk_count'],
            audio_meta['duration_seconds'],
            audio_meta['bytes'] / 1_048_576,
            time.monotonic() - t0,
        )
        result['rendered_audio'] = True
        result['audio_path'] = str(audio_path)

    # Phase 4: Upload
    if upload_audio:
        if audio_meta is None:
            raise ValueError('Audio must be rendered before upload')
        t0 = time.monotonic()
        remote_key = f"{settings.r2_audio_prefix.rstrip('/')}/{audio_name}"
        audio_url = upload_file(audio_path, remote_key, local_preview=local_preview)
        logger.info("Upload completed: %s in %.1fs", remote_key, time.monotonic() - t0)
        result['uploaded_audio'] = True
    else:
        audio_url = ''

    # Phase 5: Publish feed
    if publish_feed:
        if not audio_url or audio_meta is None:
            raise ValueError('Audio upload is required before publishing the feed')
        episode = PublishedEpisode(
            date=run_date,
            title=draft.episode_title,
            slug=safe_slug(draft.episode_title),
            summary=draft.episode_summary,
            audio_url=audio_url,
            audio_bytes=audio_meta['bytes'],
            duration_seconds=audio_meta['duration_seconds'],
            source_manifest_url=f"{settings.site_base_url}/sources/{run_date}.html",
            published_at=iso_now(),
        )
        fingerprints = [fingerprint(s['title'], s['url']) for s in manifest['sources']]
        source_titles = [s['title'] for s in manifest['sources']]
        publish_episode(episode, fingerprints, source_titles)
        result['published'] = True
        result['audio_url'] = audio_url
        logger.info("Feed published: %s", draft.episode_title)

    total_elapsed = time.monotonic() - pipeline_start
    result['pipeline_seconds'] = round(total_elapsed, 1)
    logger.info("Pipeline completed in %.1fs", total_elapsed)

    write_json(outputs_dir / 'run_summary.json', result)
    return result
