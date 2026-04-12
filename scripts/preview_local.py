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
    parser = argparse.ArgumentParser(description='Local preview: script + optional audio, no upload/publish')
    parser.add_argument('--date', default='today', help="YYYY-MM-DD or 'today'")
    parser.add_argument('--skip-audio', action='store_true', help='Generate only the script')
    args = parser.parse_args()
    run_date = date.today().isoformat() if args.date == 'today' else args.date
    result = run_pipeline(
        run_date=run_date,
        local_preview=True,
        render_audio=not args.skip_audio,
        upload_audio=False,
        publish_feed=False,
    )
    print(result)


if __name__ == '__main__':
    main()
