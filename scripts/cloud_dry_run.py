from __future__ import annotations

import argparse
import logging
from datetime import date

from ai_press_review.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    parser = argparse.ArgumentParser(description='Cloud dry run: remote LLM + Cartesia, no upload/publish')
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--profile', default='daily', help='Editorial profile: daily, weekly_recap')
    parser.add_argument('--render-audio', dest='render_audio', action='store_true', default=True,
                        help='Render TTS audio (default: on)')
    parser.add_argument('--no-render-audio', dest='render_audio', action='store_false',
                        help='Skip TTS rendering (useful to isolate collect/editorial)')
    args = parser.parse_args()
    profile = (args.profile or '').strip() or 'daily'
    result = run_pipeline(
        run_date=args.date,
        local_preview=False,
        render_audio=args.render_audio,
        upload_audio=False,
        publish_feed=False,
        profile=profile,
    )
    print(result)


if __name__ == '__main__':
    main()
