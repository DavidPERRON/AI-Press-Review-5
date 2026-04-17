#!/usr/bin/env python3
"""One-time OAuth2 setup — run locally to obtain YOUTUBE_REFRESH_TOKEN.

Prerequisites:
  1. Go to https://console.cloud.google.com
  2. Create a project (or select an existing one)
  3. Enable "YouTube Data API v3"
     → APIs & Services → Enable APIs → search "YouTube Data API v3"
  4. Create OAuth 2.0 credentials
     → APIs & Services → Credentials → Create Credentials → OAuth client ID
     → Application type: "Desktop app"
     → Download the JSON file (client_secret_XXXX.json)

Usage:
    python scripts/youtube_auth_setup.py --credentials ~/Downloads/client_secret_XXXX.json

After completing the browser consent flow, the script prints three values:
    YOUTUBE_CLIENT_ID
    YOUTUBE_CLIENT_SECRET
    YOUTUBE_REFRESH_TOKEN

Add all three as GitHub Secrets:
    Repo → Settings → Secrets and variables → Actions → New repository secret
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obtain a YouTube refresh token via OAuth2 consent flow"
    )
    parser.add_argument(
        "--credentials",
        required=True,
        metavar="PATH",
        help="Path to your client_secret_XXXX.json downloaded from Google Cloud Console",
    )
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    if not creds_path.exists():
        sys.exit(f"ERROR: File not found: {creds_path}")

    try:
        raw = json.loads(creds_path.read_text())
        info = raw.get("installed") or raw.get("web")
        if not info:
            sys.exit("ERROR: Unexpected credentials JSON format — expected 'installed' or 'web' key")
        client_id = info["client_id"]
        client_secret = info["client_secret"]
    except (json.JSONDecodeError, KeyError) as exc:
        sys.exit(f"ERROR: Could not parse credentials file: {exc}")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        sys.exit(
            "ERROR: google-auth-oauthlib is not installed.\n"
            "  → pip install google-auth-oauthlib"
        )

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
    ]

    print("\nStarting OAuth2 consent flow — your browser will open.")
    print("Log in with the YouTube channel owner's Google account.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes=scopes)
    creds = flow.run_local_server(port=0, open_browser=True)

    refresh_token = creds.refresh_token
    if not refresh_token:
        sys.exit(
            "ERROR: No refresh token returned.\n"
            "  → Revoke existing app access at https://myaccount.google.com/permissions\n"
            "    and run this script again."
        )

    print("\n" + "=" * 60)
    print("SUCCESS — add these three values as GitHub Secrets:")
    print("  Repo → Settings → Secrets and variables → Actions")
    print("=" * 60)
    print(f"\nYOUTUBE_CLIENT_ID\n  {client_id}\n")
    print(f"YOUTUBE_CLIENT_SECRET\n  {client_secret}\n")
    print(f"YOUTUBE_REFRESH_TOKEN\n  {refresh_token}\n")
    print("=" * 60)
    print("\nOptional: set these repo Variables (not Secrets) for playlist integration:")
    print("  YOUTUBE_PLAYLIST_ID_EN   — your EN daily playlist ID")
    print("  YOUTUBE_PLAYLIST_ID_FR   — your FR daily playlist ID")
    print("\nFind a playlist ID in its URL: youtube.com/playlist?list=<THIS PART>")
    print("  EN: PLwGlRWhh3Zq_BmVMFSEr6CyRyJpwK1s9r (current static playlist)")


if __name__ == "__main__":
    main()
