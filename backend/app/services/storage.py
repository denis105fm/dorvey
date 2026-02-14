"""S3-compatible storage (MinIO, Cloudflare R2)."""

from typing import Optional
from app.core.config import settings


def _client():
    """Lazy boto3 S3 client."""
    import boto3
    from botocore.config import Config
    cfg = Config(signature_version="s3v4", retries={"max_attempts": 2, "mode": "standard"})
    kw = {
        "service_name": "s3",
        "region_name": settings.S3_REGION,
        "config": cfg,
    }
    if settings.S3_ENDPOINT_URL:
        kw["endpoint_url"] = settings.S3_ENDPOINT_URL
    if settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY:
        kw["aws_access_key_id"] = settings.S3_ACCESS_KEY
        kw["aws_secret_access_key"] = settings.S3_SECRET_KEY
    return boto3.client(**kw)


def is_available() -> bool:
    """True if S3/MinIO is configured."""
    return bool(settings.S3_ACCESS_KEY and settings.S3_SECRET_KEY and settings.S3_BUCKET)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> Optional[str]:
    """Upload bytes. Returns public URL or None."""
    if not is_available():
        return None
    try:
        client = _client()
        client.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        if settings.S3_ENDPOINT_URL and "minio" in settings.S3_ENDPOINT_URL.lower():
            return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{key}"
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{key}"
    except Exception:
        return None


def upload_html(key: str, html: str) -> Optional[str]:
    """Upload HTML content."""
    return upload_bytes(key, html.encode("utf-8"), content_type="text/html; charset=utf-8")


def get_presigned_url(key: str, expires_in: int = 3600) -> Optional[str]:
    """Generate presigned URL for download."""
    if not is_available():
        return None
    try:
        client = _client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    except Exception:
        return None


def delete(key: str) -> bool:
    """Delete object. Returns success."""
    if not is_available():
        return False
    try:
        client = _client()
        client.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except Exception:
        return False
