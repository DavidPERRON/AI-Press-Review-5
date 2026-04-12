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
    args = parser.parse_args()
    result = run_pipeline(
        run_date=args.date,
        local_preview=False,
        render_audio=True,
        upload_audio=False,
        publish_feed=False,
    )
    print(result)


if __name__ == '__main__':
    main()
