from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import time
import uuid
import wave
from pathlib import Path

import websockets

from ..settings import load_settings

logger = logging.getLogger(__name__)

CARTESIA_WEBSOCKET_URL = 'wss://api.cartesia.ai/tts/websocket'

# Phase 8 / T5: raw PCM sample rate for the websocket stream. 44.1kHz matches
# the previous /tts/bytes WAV output (pcm_f32le @ 44100) at half the bandwidth
# (16-bit vs 32-bit) with no audible loss for speech.
WEBSOCKET_SAMPLE_RATE = 44100


def split_script(text: str, max_chars: int = 1800) -> list[str]:
    """Split the script into paragraph-aligned chunks under max_chars each.

    Each chunk is sent as a separate transcript within a single shared
    context_id websocket session, so Cartesia keeps prosody and voice state
    across the whole script. There are no per-chunk restart artefacts.
    """
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks: list[str] = []
    current = ''
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def synthesize_script(script: str, output_path: Path, local_preview: bool = False) -> dict:
    """Render the full script as a single continuous MP3 via websocket continuity.

    Phase 8 / T5: replaced /tts/bytes per-chunk POSTs (plus post-hoc pydub
    crossfade) with /tts/websocket on a shared context_id. Test C user
    ear-test confirmed seams are inaudible under continuity mode — the
    model treats the whole script as one utterance, so there are no
    independent "chunk restart" transients and no inter-chunk level mismatch.
    """
    from pydub import AudioSegment

    settings = load_settings(local_preview=local_preview)
    if not settings.cartesia_api_key:
        raise ValueError('CARTESIA_API_KEY is required for TTS')
    if not settings.cartesia_voice_id:
        raise ValueError('CARTESIA_VOICE_ID is required for TTS')

    chunks = split_script(script, max_chars=settings.tts_chunk_max_chars)
    if not chunks:
        raise ValueError('Script is empty — cannot synthesize audio')

    output_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    raw_pcm = asyncio.run(_render_script_websocket(chunks, settings))
    elapsed = time.monotonic() - start

    # Wrap raw PCM (int16 little-endian mono) into a WAV, then transcode to MP3.
    tmp_wav = output_path.parent / 'tts_raw.wav'
    with wave.open(str(tmp_wav), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # pcm_s16le = 2 bytes per sample
        wf.setframerate(WEBSOCKET_SAMPLE_RATE)
        wf.writeframes(raw_pcm)

    segment = AudioSegment.from_file(tmp_wav, format='wav')
    segment.export(output_path, format='mp3', bitrate=settings.tts_bitrate)
    tmp_wav.unlink(missing_ok=True)

    duration_seconds = math.ceil(len(segment) / 1000)
    logger.info(
        'TTS synthesized: chunks=%d raw_bytes=%d duration=%ds elapsed=%.1fs',
        len(chunks), len(raw_pcm), duration_seconds, elapsed,
    )

    return {
        'chunk_count': len(chunks),
        'duration_seconds': duration_seconds,
        'bytes': output_path.stat().st_size,
    }


async def _render_script_websocket(chunks: list[str], settings, max_retries: int = 3) -> bytes:
    """Retry the whole session up to max_retries times on failure.

    Partial audio from a dropped session isn't useful — a seam-free episode
    requires a single uninterrupted websocket session from start to finish.
    Retries back off exponentially (capped at 15s).
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return await _render_session(chunks, settings)
        except Exception as exc:
            last_exc = exc
            logger.warning('Cartesia websocket attempt %d/%d failed: %s', attempt, max_retries, exc)
            if attempt < max_retries:
                await asyncio.sleep(min(2 ** attempt, 15))
    raise ValueError(f'Cartesia websocket failed after {max_retries} attempts: {last_exc}')


async def _render_session(chunks: list[str], settings) -> bytes:
    context_id = f'aipr-{uuid.uuid4()}'
    url = (
        f'{CARTESIA_WEBSOCKET_URL}'
        f'?cartesia_version={settings.cartesia_version}'
        f'&api_key={settings.cartesia_api_key}'
    )

    # max_size=None lifts the default 1 MiB per-frame cap — audio frames for
    # long scripts can exceed that. Default ping_interval (20s) is fine since
    # Cartesia streams audio frames continuously to keep the connection live.
    async with websockets.connect(url, max_size=None) as ws:
        for i, chunk in enumerate(chunks, start=1):
            is_last = (i == len(chunks))
            request = {
                'model_id': settings.cartesia_model_id,
                'transcript': chunk,
                'voice': {'mode': 'id', 'id': settings.cartesia_voice_id},
                'language': settings.cartesia_language,
                'context_id': context_id,
                'continue': not is_last,
                'output_format': {
                    'container': 'raw',
                    'encoding': 'pcm_s16le',
                    'sample_rate': WEBSOCKET_SAMPLE_RATE,
                },
                'generation_config': {
                    'volume': settings.cartesia_volume,
                    'speed': settings.cartesia_speed,
                    'emotion': settings.cartesia_emotion,
                },
            }
            await ws.send(json.dumps(request))

        audio = bytearray()
        while True:
            msg = json.loads(await ws.recv())
            if msg.get('context_id') != context_id:
                continue  # ignore any stale frames from a prior session
            mtype = msg.get('type')
            if mtype == 'chunk':
                audio.extend(base64.b64decode(msg['data']))
            elif mtype == 'done':
                break
            elif mtype == 'error':
                raise RuntimeError(f'Cartesia error: {msg}')
    return bytes(audio)
