from __future__ import annotations

import math
from pathlib import Path

import requests

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


def _trim_silence(segment, silence_thresh_db: float = -45.0, chunk_ms: int = 10):
    """Trim leading/trailing silence from a pydub AudioSegment.

    Keeps a tiny head (10ms) so we don't clip a starting consonant.
    """
    from pydub.silence import detect_leading_silence

    lead = detect_leading_silence(segment, silence_threshold=silence_thresh_db, chunk_size=chunk_ms)
    trail = detect_leading_silence(segment.reverse(), silence_threshold=silence_thresh_db, chunk_size=chunk_ms)
    head_keep = 10
    start = max(0, lead - head_keep)
    end = len(segment) - max(0, trail - head_keep)
    if end <= start:
        return segment
    return segment[start:end]


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
        seg = AudioSegment.from_file(chunk_path, format='wav')
        seg = _trim_silence(seg)
        rendered.append(seg)

    # Concatenate chunks with a short crossfade + a natural paragraph pause
    # to hide the seams between Cartesia renders.
    crossfade_ms = 60
    pause_ms = 220
    pause = AudioSegment.silent(duration=pause_ms, frame_rate=rendered[0].frame_rate)

    combined = rendered[0]
    for seg in rendered[1:]:
        combined = combined.append(pause, crossfade=0)
        combined = combined.append(seg, crossfade=crossfade_ms)

    combined.export(output_path, format='mp3', bitrate='128k')
    return {
        'chunk_count': len(chunks),
        'duration_seconds': math.ceil(len(combined) / 1000),
        'bytes': output_path.stat().st_size,
    }


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
