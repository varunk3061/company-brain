"""Private Cloudflare R2 bucket that holds the original PDFs.

Only the backend talks to the bucket. The browser never gets the keys; it only receives
short-lived presigned links, and only after the access policy has said yes.
"""

import logging
import os
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------------

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET = os.getenv("R2_BUCKET", "").strip()

# R2 accepts 1 second .. 7 days. Keep view links short.
PRESIGNED_URL_TTL_SECONDS = min(max(int(os.getenv("PRESIGNED_URL_TTL_SECONDS") or 300), 1), 604800)

OBJECT_PREFIX = "documents/"

# Created on first use so the API and the test-suite start without contacting R2.
_client = None

#-------------------------------------------------------------------------------------

def is_configured() -> bool:
    return all((R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET))


def _get_client():
    global _client

    if _client is None:
        if not is_configured():
            logger.error("R2 storage is not configured: set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET.")
            raise HTTPException(status_code=500, detail="Document storage is not configured.")

        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",  # required by the SDK, ignored by R2
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=10,
                read_timeout=60,
            ),
        )

    return _client


def _storage_errors():
    from botocore.exceptions import BotoCoreError, ClientError
    return BotoCoreError, ClientError

#-------------------------------------------------------------------------------------

def object_key_for(document_uuid: str) -> str:
    """Bucket key for a document. Built from the UUID, never from the uploaded file name."""
    return f"{OBJECT_PREFIX}{document_uuid}.pdf"


def put_pdf(object_key: str, data: bytes, content_hash: str) -> None:
    client = _get_client()

    try:
        client.put_object(
            Bucket=R2_BUCKET,
            Key=object_key,
            Body=data,
            ContentType="application/pdf",
            Metadata={"sha256": content_hash},
        )
    except _storage_errors() as exc:
        logger.error("R2 upload failed for %s: %s", object_key, exc)
        raise HTTPException(status_code=502, detail="Could not store the document. Please try again.") from exc


def get_pdf_bytes(object_key: str) -> bytes:
    client = _get_client()
    BotoCoreError, ClientError = _storage_errors()

    try:
        response = client.get_object(Bucket=R2_BUCKET, Key=object_key)
        return response["Body"].read()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        logger.error("R2 download failed for %s: %s", object_key, code or exc)
        if code in ("NoSuchKey", "404", "NotFound"):
            raise HTTPException(status_code=404, detail="The stored file for this document was not found.") from exc
        raise HTTPException(status_code=502, detail="Could not read the stored document.") from exc
    except BotoCoreError as exc:
        logger.error("R2 download failed for %s: %s", object_key, exc)
        raise HTTPException(status_code=502, detail="Could not read the stored document.") from exc


def delete_object(object_key: str) -> None:
    """Delete one object. Deleting a key that does not exist succeeds (idempotent)."""

    client = _get_client()

    try:
        client.delete_object(Bucket=R2_BUCKET, Key=object_key)
    except _storage_errors() as exc:
        logger.error("R2 delete failed for %s: %s", object_key, exc)
        raise HTTPException(status_code=502, detail="Could not delete the stored document. Please try again.") from exc


def presigned_view_url(object_key: str, filename: str, ttl_seconds: int = PRESIGNED_URL_TTL_SECONDS) -> str:
    """Short-lived GET link that opens the PDF inline in the browser."""

    client = _get_client()

    # ASCII fallback plus the RFC 5987 form for non-ASCII names.
    ascii_name = "".join(c for c in filename if 32 <= ord(c) < 127 and c not in '"\\') or "document.pdf"
    disposition = f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"

    try:
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": R2_BUCKET,
                "Key": object_key,
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=ttl_seconds,
        )
    except _storage_errors() as exc:
        logger.error("Presigning failed for %s: %s", object_key, exc)
        raise HTTPException(status_code=502, detail="Could not create a link to the document.") from exc
