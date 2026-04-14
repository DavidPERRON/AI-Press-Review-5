from __future__ import annotations

import argparse
import logging
from datetime import date

from ai_press_review.pipeline import generate_draft

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    parser = argparse.ArgumentParser(description='Generate draft episode (collect + LLM + TTS + upload, no RSS publish)')
    parser.add_argument('--date', default=date.today().isoformat())
    parser.add_argument('--profile', default='daily', help='Editorial profile: daily, weekly_recap')
    args = parser.parse_args()
    run_date = (args.date or '').strip() or date.today().isoformat()
    profile = (args.profile or '').strip() or 'daily'
    result = generate_draft(
        run_date=run_date,
        profile=profile,
    )
    print(result)


if __name__ == '__main__':
    main()
