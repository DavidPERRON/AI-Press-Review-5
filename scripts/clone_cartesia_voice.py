from __future__ import annotations

import argparse
from pathlib import Path

import requests

API_URL = 'https://api.cartesia.ai/voices/clone'


def main() -> None:
    parser = argparse.ArgumentParser(description='Create an instant Cartesia voice clone from a short sample')
    parser.add_argument('sample_file', help='Path to a 5-10 second clean voice sample')
    parser.add_argument('--api-key', required=True)
    parser.add_argument('--name', default='David Perron')
    parser.add_argument('--description', default='AI Press Review cloned voice')
    parser.add_argument('--language', default='en')
    args = parser.parse_args()

    sample_path = Path(args.sample_file)
    if not sample_path.exists():
        raise FileNotFoundError(sample_path)

    headers = {
        'Authorization': f'Bearer {args.api_key}',
        'Cartesia-Version': '2025-04-16',
    }
    with sample_path.open('rb') as handle:
        response = requests.post(
            API_URL,
            headers=headers,
            files={'clip': handle},
            data={
                'name': args.name,
                'description': args.description,
                'language': args.language,
            },
            timeout=180,
        )
    response.raise_for_status()
    print(response.json())


if __name__ == '__main__':
    main()
