from __future__ import annotations

import logging

from ai_press_review.pipeline import reject_pending_draft

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


def main() -> None:
    result = reject_pending_draft()
    print(f"Rejected: {result['title']} ({result['date']})")


if __name__ == '__main__':
    main()
