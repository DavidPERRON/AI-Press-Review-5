from __future__ import annotations

from pathlib import Path

import boto3

from ..settings import load_settings


def r2_client(local_preview: bool = False):
    settings = load_settings(local_preview=local_preview)
    return boto3.client(
        's3',
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name=settings.r2_region,
    )


def upload_file(
    local_path: Path,
    remote_key: str,
    content_type: str = 'audio/mpeg',
    local_preview: bool = False,
) -> str:
    settings = load_settings(local_preview=local_preview)
    client = r2_client(local_preview=local_preview)
    client.upload_file(
        str(local_path),
        settings.r2_bucket_name,
        remote_key,
        ExtraArgs={'ContentType': content_type, 'CacheControl': 'public, max-age=86400'},
    )
    return f"{settings.public_audio_base_url.rstrip('/')}/{remote_key}"


def delete_key(remote_key: str, local_preview: bool = False) -> None:
    settings = load_settings(local_preview=local_preview)
    r2_client(local_preview=local_preview).delete_object(
        Bucket=settings.r2_bucket_name,
        Key=remote_key,
    )
