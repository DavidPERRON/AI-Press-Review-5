#!/usr/bin/env python3
"""Upload the latest released episode to YouTube and add it to the playlist.

CI usage (called by .github/workflows/youtube-upload.yml after approve-release):
    python scripts/youtube_upload.py --locale en
    python scripts/youtube_upload.py --locale fr

Backfill a specific date:
    python scripts/youtube_upload.py --locale en --date 2026-04-16

If YOUTUBE_CLIENT_ID or YOUTUBE_REFRESH_TOKEN are absent the script exits 0
(soft skip), so the workflow never fails on repos that haven't wired YouTube up.

Required GitHub Secrets:
    YOUTUBE_CLIENT_ID        Google OAuth2 client ID
    YOUTUBE_CLIENT_SECRET    Google OAuth2 client secret
    YOUTUBE_REFRESH_TOKEN    Long-lived refresh token (see scripts/youtube_auth_setup.py)

Optional repo Variables (Actions → Variables):
    YOUTUBE_PLAYLIST_ID_EN   Daily EN playlist — video added after upload
    YOUTUBE_PLAYLIST_ID_FR   Daily FR playlist — video added after upload

One-time auth setup (run locally):
    python scripts/youtube_auth_setup.py --credentials ~/path/to/client_secret.json
    → Opens browser, completes OAuth consent, prints YOUTUBE_REFRESH_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tempfile
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COVER_PATH = Path("assets/podcast-cover.png")
STATE_DIR = Path("data/state")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# YouTube category IDs — 25 = News & Politics (best fit for AI news briefing)
CATEGORY_ID = "25"

_EN_TAGS = [
    "AI", "artificial intelligence", "machine learning", "AI news",
    "podcast", "press review", "tech news", "OpenAI", "ChatGPT",
    "AI Press Review",
]
_FR_TAGS = [
    "IA", "intelligence artificielle", "podcast", "revue de presse",
    "actualité IA", "machine learning", "technologie", "Revue de Presse IA",
]

_EN_DESCRIPTION = """{summary}

📻 Subscribe: https://podcast.aequitus.net/subscribe.html
📖 Episode page: https://podcast.aequitus.net/episodes/{date}.html
🌐 Website: https://podcast.aequitus.net

Your daily AI press briefing — 15–20 minutes, published every weekday morning.

#AI #ArtificialIntelligence #MachineLearning #AINews #Podcast #TechNews"""

_FR_DESCRIPTION = """{summary}

📻 S'abonner : https://podcast.aequitus.net/fr/subscribe.html
📖 Épisode : https://podcast.aequitus.net/fr/episodes/{date}.html
🌐 Site : https://podcast.aequitus.net/fr

Votre revue de presse IA quotidienne — 15 à 20 minutes, publiée chaque matin en semaine.

#IA #IntelligenceArtificielle #MachineLearning #Podcast #Technologie"""


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _get_credentials() -> Credentials:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    missing = [k for k, v in {
        "YOUTUBE_CLIENT_ID": client_id,
        "YOUTUBE_CLIENT_SECRET": client_secret,
        "YOUTUBE_REFRESH_TOKEN": refresh_token,
    }.items() if not v]
    if missing:
        sys.exit(
            f"ERROR: Missing YouTube credentials: {', '.join(missing)}\n"
            "  → Add them as GitHub Secrets (Settings → Secrets and variables → Actions)\n"
            "  → Run scripts/youtube_auth_setup.py locally to obtain YOUTUBE_REFRESH_TOKEN"
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------

def _load_episode(locale: str, date: str | None) -> dict:
    path = STATE_DIR / f"episode_history_{locale}.json"
    if not path.exists():
        sys.exit(f"ERROR: State file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    episodes = data.get("episodes", [])
    if not episodes:
        sys.exit(f"ERROR: No episodes in {path}")
    if date:
        matches = [e for e in episodes if e.get("date") == date]
        if not matches:
            sys.exit(f"ERROR: No episode with date={date!r} in {path}")
        return matches[0]
    return episodes[0]  # most recent first


def _download_audio(url: str, dest: Path) -> None:
    print(f"  Downloading audio from R2…")
    resp = requests.get(url, stream=True, timeout=180)
    resp.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65_536):
            fh.write(chunk)
    mb = dest.stat().st_size / 1_048_576
    print(f"  Audio saved ({mb:.1f} MB)")


def _encode_video(audio_path: Path, cover_path: Path, output_path: Path) -> None:
    """Convert MP3 + static cover image → 1280×1280 MP4 (YouTube-compatible)."""
    print("  Encoding MP4 (ffmpeg)…")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover_path),
        "-i", str(audio_path),
        "-vf", "scale=1280:1280",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "fast", "-crf", "28",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ERROR: ffmpeg failed:\n{result.stderr[-2000:]}")
    mb = output_path.stat().st_size / 1_048_576
    print(f"  Video encoded ({mb:.1f} MB)")


# ---------------------------------------------------------------------------
# YouTube API helpers
# ---------------------------------------------------------------------------

def _upload_video(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    language: str,
) -> str:
    """Upload video with chunked resumable upload; return video_id."""
    body = {
        "snippet": {
            "title": title[:100],           # YouTube 100-char limit
            "description": description[:5000],
            "tags": tags,
            "categoryId": CATEGORY_ID,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=5 * 1024 * 1024,   # 5 MB chunks
        resumable=True,
    )
    print(f"  Uploading: {title!r}")
    req = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            print(f"    {int(status.progress() * 100)}%…")
    video_id = response["id"]
    print(f"  Uploaded → https://youtube.com/watch?v={video_id}")
    return video_id


def _set_thumbnail(youtube, video_id: str, cover_path: Path) -> None:
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(str(cover_path), mimetype="image/png"),
        ).execute()
        print("  Thumbnail set.")
    except HttpError as exc:
        # Thumbnail upload requires a verified channel; warn but don't fail.
        print(f"  Warning: thumbnail not set ({exc.status_code}): {exc.reason}")


def _add_to_playlist(youtube, video_id: str, playlist_id: str) -> None:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()
    print(f"  Added to playlist → https://youtube.com/playlist?list={playlist_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Upload latest episode to YouTube")
    parser.add_argument("--locale", choices=["en", "fr"], default="en", help="Locale (en or fr)")
    parser.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                        help="Specific episode date to upload (defaults to latest)")
    args = parser.parse_args()
    locale: str = args.locale

    # ── Soft skip if credentials are not configured ──────────────────────────
    if not (os.environ.get("YOUTUBE_CLIENT_ID") and os.environ.get("YOUTUBE_REFRESH_TOKEN")):
        print("YouTube credentials not configured — skipping upload.")
        print("Run scripts/youtube_auth_setup.py locally to set up, then add secrets to GitHub.")
        return

    # ── Load episode metadata ────────────────────────────────────────────────
    episode = _load_episode(locale, args.date)
    title = episode["title"]
    summary = episode.get("summary", "")
    date = episode["date"]
    audio_url = episode["audio_url"]
    print(f"\n→ Episode: {title!r}  [{locale.upper()}]  ({date})")

    # ── Build description + tags ─────────────────────────────────────────────
    if locale == "fr":
        description = _FR_DESCRIPTION.format(summary=summary, date=date)
        tags = _FR_TAGS
        language = "fr"
        playlist_id = os.environ.get("YOUTUBE_PLAYLIST_ID_FR", "").strip()
    else:
        description = _EN_DESCRIPTION.format(summary=summary, date=date)
        tags = _EN_TAGS
        language = "en"
        playlist_id = os.environ.get("YOUTUBE_PLAYLIST_ID_EN", "").strip()

    # ── Build YouTube client ─────────────────────────────────────────────────
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # ── Work in a temp directory ─────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        audio_path = tmpdir / "episode.mp3"
        video_path = tmpdir / "episode.mp4"

        t0 = time.monotonic()
        _download_audio(audio_url, audio_path)
        _encode_video(audio_path, COVER_PATH, video_path)
        video_id = _upload_video(youtube, video_path, title, description, tags, language)

        _set_thumbnail(youtube, video_id, COVER_PATH)

        if playlist_id:
            _add_to_playlist(youtube, video_id, playlist_id)
        else:
            env_var = f"YOUTUBE_PLAYLIST_ID_{locale.upper()}"
            print(f"  {env_var} not set — video uploaded but not added to a playlist.")

        elapsed = time.monotonic() - t0

    print(f"\n✅ YouTube upload complete in {elapsed:.0f}s")
    print(f"   Video URL : https://youtube.com/watch?v={video_id}")
    if playlist_id:
        print(f"   Playlist  : https://youtube.com/playlist?list={playlist_id}")


if __name__ == "__main__":
    main()
