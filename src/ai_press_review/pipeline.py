from __future__ import annotations

import logging
import time
from pathlib import Path

from .collect import collect_sources
from .editorial.generator import generate_episode_script
from .models import PublishedEpisode
from .observability import record_phase, record_run
from .publish.feed import publish_episode
from .settings import load_settings
from .state import delete_pending_draft, load_pending_draft, save_pending_draft
from .storage.r2 import delete_key, upload_file
from .tts.cartesia import synthesize_script
from .utils import fingerprint, iso_now, safe_slug, write_json

logger = logging.getLogger(__name__)


def run_pipeline(
    run_date: str,
    local_preview: bool = False,
    render_audio: bool = True,
    upload_audio: bool = False,
    publish_feed: bool = False,
    profile: str | None = None,
) -> dict:
    pipeline_start = time.monotonic()
    settings = load_settings(local_preview=local_preview, profile=profile)
    logger.info("Pipeline started: date=%s preview=%s profile=%s", run_date, local_preview, settings.profile_name)

    # Phase 1: Collect
    t0 = time.monotonic()
    manifest = collect_sources(run_date=run_date, local_preview=local_preview, profile=profile)
    elapsed = time.monotonic() - t0
    logger.info("Collection completed: %d sources in %.1fs", manifest['source_count'], elapsed)
    record_phase(run_date, 'collect', elapsed, source_count=manifest['source_count'], profile=settings.profile_name)

    # Phase 2: Generate editorial script
    t0 = time.monotonic()
    draft = generate_episode_script(manifest, local_preview=local_preview, profile=profile)
    elapsed = time.monotonic() - t0
    word_count = len(draft.script.split())
    logger.info("Editorial completed: %d words in %.1fs", word_count, elapsed)
    record_phase(run_date, 'editorial', elapsed, word_count=word_count, profile=settings.profile_name)

    outputs_dir = Path('output') / run_date
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / 'script.txt').write_text(draft.script, encoding='utf-8')
    (outputs_dir / 'episode_summary.txt').write_text(draft.episode_summary, encoding='utf-8')

    result = {
        'run_date': run_date,
        'profile': settings.profile_name,
        'source_count': manifest['source_count'],
        'script_title': draft.episode_title,
        'script_words': word_count,
        'rendered_audio': False,
        'uploaded_audio': False,
        'published': False,
        'grounding_report': draft.grounding_report,
    }

    audio_name = f"{run_date}-{safe_slug(draft.episode_title)}.mp3"
    audio_path = outputs_dir / audio_name
    audio_meta = None

    # Phase 3: TTS
    if render_audio:
        t0 = time.monotonic()
        audio_meta = synthesize_script(draft.script, audio_path, local_preview=local_preview)
        elapsed = time.monotonic() - t0
        logger.info(
            "TTS completed: %d chunks, %ds duration, %.1f MB in %.1fs",
            audio_meta['chunk_count'],
            audio_meta['duration_seconds'],
            audio_meta['bytes'] / 1_048_576,
            elapsed,
        )
        record_phase(
            run_date, 'tts', elapsed,
            chunks=audio_meta['chunk_count'],
            audio_duration_s=audio_meta['duration_seconds'],
            audio_bytes=audio_meta['bytes'],
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
        elapsed = time.monotonic() - t0
        logger.info("Upload completed: %s in %.1fs", remote_key, elapsed)
        record_phase(run_date, 'upload', elapsed, remote_key=remote_key)
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
        t0 = time.monotonic()
        fingerprints = [fingerprint(s['title'], s['url']) for s in manifest['sources']]
        source_titles = [s['title'] for s in manifest['sources']]
        publish_episode(episode, fingerprints, source_titles)
        elapsed = time.monotonic() - t0
        record_phase(run_date, 'publish', elapsed, title=draft.episode_title)
        result['published'] = True
        result['audio_url'] = audio_url
        logger.info("Feed published: %s", draft.episode_title)

    total_elapsed = time.monotonic() - pipeline_start
    result['pipeline_seconds'] = round(total_elapsed, 1)
    logger.info("Pipeline completed in %.1fs", total_elapsed)

    record_run(
        run_date,
        profile=settings.profile_name,
        source_count=manifest['source_count'],
        script_title=draft.episode_title,
        script_words=word_count,
        audio_duration_s=(audio_meta or {}).get('duration_seconds'),
        rendered=result['rendered_audio'],
        uploaded=result['uploaded_audio'],
        published=result['published'],
        grounding_coverage=draft.grounding_report.get('coverage_ratio'),
        grounding_acceptable=draft.grounding_report.get('acceptable'),
        claim_count=draft.grounding_report.get('claim_count'),
        pipeline_seconds=round(total_elapsed, 1),
    )

    write_json(outputs_dir / 'run_summary.json', result)
    return result


# ── Draft workflow functions ─────────────────────────────────


def generate_draft(
    run_date: str,
    profile: str = 'daily',
    local_preview: bool = False,
) -> dict:
    """Collect, generate, render audio, upload — but do NOT publish to RSS.
    Saves draft metadata for later release or rejection."""
    pipeline_start = time.monotonic()
    settings = load_settings(local_preview=local_preview, profile=profile)
    logger.info("Draft generation started: date=%s profile=%s", run_date, profile)

    # Phase 1: Collect
    t0 = time.monotonic()
    manifest = collect_sources(run_date=run_date, local_preview=local_preview, profile=profile)
    elapsed = time.monotonic() - t0
    logger.info("Collection completed: %d sources in %.1fs", manifest['source_count'], elapsed)
    record_phase(run_date, 'collect', elapsed, source_count=manifest['source_count'], profile=profile)

    # Phase 2: Generate
    t0 = time.monotonic()
    draft = generate_episode_script(manifest, local_preview=local_preview, profile=profile)
    elapsed = time.monotonic() - t0
    word_count = len(draft.script.split())
    logger.info("Editorial completed: %d words in %.1fs", word_count, elapsed)
    record_phase(run_date, 'editorial', elapsed, word_count=word_count, profile=profile)

    outputs_dir = Path('output') / run_date
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / 'script.txt').write_text(draft.script, encoding='utf-8')
    (outputs_dir / 'episode_summary.txt').write_text(draft.episode_summary, encoding='utf-8')

    # Phase 3: TTS
    audio_name = f"{run_date}-{safe_slug(draft.episode_title)}.mp3"
    audio_path = outputs_dir / audio_name
    t0 = time.monotonic()
    audio_meta = synthesize_script(draft.script, audio_path, local_preview=local_preview)
    elapsed = time.monotonic() - t0
    logger.info(
        "TTS completed: %d chunks, %ds duration, %.1f MB in %.1fs",
        audio_meta['chunk_count'],
        audio_meta['duration_seconds'],
        audio_meta['bytes'] / 1_048_576,
        elapsed,
    )
    record_phase(
        run_date, 'tts', elapsed,
        chunks=audio_meta['chunk_count'],
        audio_duration_s=audio_meta['duration_seconds'],
        audio_bytes=audio_meta['bytes'],
    )

    # Phase 4: Upload audio (so user can preview)
    t0 = time.monotonic()
    remote_key = f"{settings.r2_audio_prefix.rstrip('/')}/{audio_name}"
    audio_url = upload_file(audio_path, remote_key, local_preview=local_preview)
    elapsed = time.monotonic() - t0
    logger.info("Upload completed: %s in %.1fs", remote_key, elapsed)
    record_phase(run_date, 'upload', elapsed, remote_key=remote_key)

    # Save draft state
    fps = [fingerprint(s['title'], s['url']) for s in manifest['sources']]
    titles = [s['title'] for s in manifest['sources']]

    draft_data = {
        'date': run_date,
        'profile': profile,
        'title': draft.episode_title,
        'slug': safe_slug(draft.episode_title),
        'summary': draft.episode_summary,
        'audio_url': audio_url,
        'audio_name': audio_name,
        'audio_bytes': audio_meta['bytes'],
        'duration_seconds': audio_meta['duration_seconds'],
        'source_manifest_url': f"{settings.site_base_url}/sources/{run_date}.html",
        'source_fingerprints': fps,
        'source_titles': titles,
        'source_count': manifest['source_count'],
        'script_words': len(draft.script.split()),
        'key_claims': draft.key_claims,
        'grounding_report': draft.grounding_report,
        'generated_at': iso_now(),
        'status': 'pending',
    }
    save_pending_draft(draft_data)

    # Surface the grounding report as an observability signal.
    if draft.grounding_report:
        record_phase(
            run_date, 'grounding', 0,
            claim_count=draft.grounding_report.get('claim_count', 0),
            supported_count=draft.grounding_report.get('supported_count', 0),
            coverage_ratio=draft.grounding_report.get('coverage_ratio', 0.0),
            acceptable=draft.grounding_report.get('acceptable', True),
        )

    total_elapsed = time.monotonic() - pipeline_start
    draft_data['pipeline_seconds'] = round(total_elapsed, 1)
    logger.info("Draft saved: %s (%d words, %ds audio) in %.1fs",
                draft.episode_title, draft_data['script_words'],
                audio_meta['duration_seconds'], total_elapsed)

    record_run(
        run_date,
        profile=profile,
        source_count=manifest['source_count'],
        script_title=draft.episode_title,
        script_words=draft_data['script_words'],
        audio_duration_s=audio_meta['duration_seconds'],
        rendered=True,
        uploaded=True,
        published=False,
        status='pending',
        pipeline_seconds=round(total_elapsed, 1),
    )

    write_json(outputs_dir / 'run_summary.json', draft_data)
    return draft_data


def release_pending_draft() -> dict:
    """Publish the pending draft to the RSS feed."""
    draft_data = load_pending_draft()
    if not draft_data or draft_data.get('status') != 'pending':
        raise ValueError('No pending draft to release')

    episode = PublishedEpisode(
        date=draft_data['date'],
        title=draft_data['title'],
        slug=draft_data['slug'],
        summary=draft_data['summary'],
        audio_url=draft_data['audio_url'],
        audio_bytes=draft_data['audio_bytes'],
        duration_seconds=draft_data['duration_seconds'],
        source_manifest_url=draft_data['source_manifest_url'],
        published_at=iso_now(),
    )

    publish_episode(
        episode,
        draft_data.get('source_fingerprints', []),
        draft_data.get('source_titles', []),
    )

    draft_data['status'] = 'released'
    draft_data['released_at'] = iso_now()
    save_pending_draft(draft_data)

    logger.info("Draft released: %s", draft_data['title'])
    return draft_data


def reject_pending_draft() -> dict:
    """Reject the pending draft and optionally delete audio from R2."""
    draft_data = load_pending_draft()
    if not draft_data or draft_data.get('status') != 'pending':
        raise ValueError('No pending draft to reject')

    if draft_data.get('audio_url'):
        settings = load_settings()
        base = settings.public_audio_base_url.rstrip('/') + '/'
        key = draft_data['audio_url'].replace(base, '')
        try:
            delete_key(key)
            logger.info("Deleted audio from R2: %s", key)
        except Exception as exc:
            logger.warning("Could not delete audio from R2: %s", exc)

    draft_data['status'] = 'rejected'
    draft_data['rejected_at'] = iso_now()
    save_pending_draft(draft_data)

    logger.info("Draft rejected: %s", draft_data['title'])
    return draft_data
