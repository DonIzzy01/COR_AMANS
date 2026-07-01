"""
Storage abstraction — local filesystem (dev) or S3/Cloudflare R2 (production).
Set STORAGE_BACKEND=s3 and S3_BUCKET / S3_ENDPOINT_URL / AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY in .env to switch to object storage.
"""
import os
import uuid
from pathlib import Path

BACKEND = os.environ.get('STORAGE_BACKEND', 'local')  # 'local' | 's3'
BUCKET  = os.environ.get('S3_BUCKET', 'cor-amans')
CDN_URL = os.environ.get('CDN_URL', '')            # e.g. https://cdn.yourdomain.com


def _s3_client():
    import boto3
    return boto3.client(
        's3',
        endpoint_url=os.environ.get('S3_ENDPOINT_URL'),      # set for R2/MinIO
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'auto'),
    )


def save_file(file_obj, folder: str, original_filename: str) -> str:
    """
    Save a file. Returns the storage key (relative path or S3 key).
    """
    ext = Path(original_filename).suffix.lower()
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    if BACKEND == 's3':
        client = _s3_client()
        file_obj.seek(0)
        client.upload_fileobj(
            file_obj, BUCKET, key,
            ExtraArgs={
                'ContentDisposition': f'inline; filename="{original_filename}"',
                'CacheControl': 'public, max-age=31536000',
            }
        )
    else:
        local_path = Path('static/uploads') / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        file_obj.seek(0)
        local_path.write_bytes(file_obj.read())

    return key


def delete_file(key: str) -> None:
    """Delete a file by its storage key."""
    if not key:
        return
    if BACKEND == 's3':
        _s3_client().delete_object(Bucket=BUCKET, Key=key)
    else:
        local_path = Path('static/uploads') / key
        local_path.unlink(missing_ok=True)


def public_url(key: str) -> str:
    """Return a publicly accessible URL for a stored file."""
    if not key:
        return ''
    if CDN_URL:
        return f"{CDN_URL.rstrip('/')}/{key}"
    if BACKEND == 's3':
        endpoint = os.environ.get('S3_ENDPOINT_URL', f"https://s3.amazonaws.com")
        return f"{endpoint.rstrip('/')}/{BUCKET}/{key}"
    return f"/static/uploads/{key}"
