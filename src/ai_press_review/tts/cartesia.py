from __future__ import annotations

import math
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..settings import load_settings

CARTESIA_TTS_URL = 'https://api.cartesia.ai/tts/bytes'


def split_script(text: str, max_chars: int = 1800) -> list[str]:
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
    chunk_dir = output_path.parent / 'tts_chunks'
    chunk_dir.mkdir(parents=True, exist_ok=True)

    rendered = []
    for index, chunk in enumerate(chunks, start=1):
        chunk_path = chunk_dir / f'chunk_{index:03d}.wav'
        chunk_path.write_bytes(_render_chunk(chunk, settings))
        rendered.append(AudioSegment.from_file(chunk_path, format='wav'))

    combined = rendered[0]
    # Phase 8 / T2 E1 (reverted): 400ms crossfade swallowed word transitions and
    # created audible "set merge" artefacts. 150ms restored — user ear-test on real
    # audio confirmed 150ms transitions are "almost inaudible". The mouth-noise
    # artefacts during natural pauses are within-chunk (Cartesia sonic-3 voice model),
    # not at seams, so crossfade doesn't help them — separate concern for voice swap.
    for seg in rendered[1:]:
        combined = combined.append(seg, crossfade=150)

    # Phase 5 / T4: bitrate read from settings (default 96k — voice-only sweet spot).
    combined.export(output_path, format='mp3', bitrate=settings.tts_bitrate)
    return {
        'chunk_count': len(chunks),
        'duration_seconds': math.ceil(len(combined) / 1000),
        'bytes': output_path.stat().st_size,
    }


@retry(wait=wait_exponential(multiplier=2, min=2, max=30), stop=stop_after_attempt(3))
def _render_chunk(chunk: str, settings) -> bytes:
    headers = {
        'Authorization': f'Bearer {settings.cartesia_api_key}',
        'Cartesia-Version': settings.cartesia_version,
        'Content-Type': 'application/json',
    }
    payload = {
        'model_id': settings.cartesia_model_id,
        'transcript': chunk,
        'voice': {'mode': 'id', 'id': settings.cartesia_voice_id},
        'output_format': {'container': 'wav', 'encoding': 'pcm_f32le', 'sample_rate': 44100},
        'language': settings.cartesia_language,
        'generation_config': {
            'volume': settings.cartesia_volume,
            'speed': settings.cartesia_speed,
            'emotion': settings.cartesia_emotion,
        },
        'save': False,
    }
    response = requests.post(CARTESIA_TTS_URL, headers=headers, json=payload, timeout=180)
    response.raise_for_status()
    return response.content
