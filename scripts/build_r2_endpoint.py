from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description='Build the R2 S3 endpoint from an account ID')
    parser.add_argument('account_id')
    args = parser.parse_args()
    print(f'https://{args.account_id}.r2.cloudflarestorage.com')


if __name__ == '__main__':
    main()
