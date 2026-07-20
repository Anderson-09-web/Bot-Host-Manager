"""Cloudflare R2 storage service using boto3 S3-compatible API."""
import io
import logging
import asyncio
from typing import List, Optional
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

logger = logging.getLogger(__name__)

# Thread pool for running boto3 (sync) in async context
_executor = ThreadPoolExecutor(max_workers=4)


def _get_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=30,
        ),
    )


async def _run_in_executor(func, *args):
    """Run a blocking boto3 call in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args)


class R2StorageService:
    """All file operations against Cloudflare R2."""

    def __init__(self):
        self.bucket = settings.R2_BUCKET_NAME

    def _client(self):
        return _get_client()

    async def list_objects(self, prefix: str = "") -> List[dict]:
        """List all objects under a prefix. Returns raw S3 objects."""
        def _list():
            client = self._client()
            results = []
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                results.extend(page.get("Contents", []))
            return results

        try:
            return await _run_in_executor(_list)
        except ClientError as e:
            logger.error("R2 list_objects error: %s", e)
            return []

    async def list_prefix(self, prefix: str = "", delimiter: str = "/") -> dict:
        """List objects and common prefixes (simulates directory listing)."""
        def _list():
            client = self._client()
            # Normalize prefix
            if prefix and not prefix.endswith("/"):
                prefix_key = prefix + "/"
            else:
                prefix_key = prefix

            result = client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix_key,
                Delimiter=delimiter,
            )
            return result

        try:
            return await _run_in_executor(_list)
        except ClientError as e:
            logger.error("R2 list_prefix error: %s", e)
            return {"Contents": [], "CommonPrefixes": []}

    async def get_object(self, key: str) -> Optional[bytes]:
        """Download an object's bytes from R2."""
        def _get():
            client = self._client()
            response = client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()

        try:
            return await _run_in_executor(_get)
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            logger.error("R2 get_object error for key=%s: %s", key, e)
            raise

    async def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """Upload bytes to R2."""
        def _put():
            client = self._client()
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )

        try:
            await _run_in_executor(_put)
            return True
        except ClientError as e:
            logger.error("R2 put_object error for key=%s: %s", key, e)
            return False

    async def delete_object(self, key: str) -> bool:
        """Delete a single object from R2."""
        def _delete():
            client = self._client()
            client.delete_object(Bucket=self.bucket, Key=key)

        try:
            await _run_in_executor(_delete)
            return True
        except ClientError as e:
            logger.error("R2 delete_object error for key=%s: %s", key, e)
            return False

    async def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a prefix. Returns count of deleted objects."""
        def _list_and_delete():
            client = self._client()
            objects = []
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                objects.extend(page.get("Contents", []))

            if not objects:
                return 0

            # Batch delete up to 1000 at a time
            deleted = 0
            for i in range(0, len(objects), 1000):
                batch = [{"Key": o["Key"]} for o in objects[i:i+1000]]
                client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": batch, "Quiet": True},
                )
                deleted += len(batch)
            return deleted

        try:
            return await _run_in_executor(_list_and_delete)
        except ClientError as e:
            logger.error("R2 delete_prefix error for prefix=%s: %s", prefix, e)
            return 0

    async def copy_object(self, source_key: str, dest_key: str) -> bool:
        """Copy an object within R2."""
        def _copy():
            client = self._client()
            client.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": source_key},
                Key=dest_key,
            )

        try:
            await _run_in_executor(_copy)
            return True
        except ClientError as e:
            logger.error("R2 copy_object error: %s", e)
            return False

    async def object_exists(self, key: str) -> bool:
        """Check if an object exists in R2."""
        def _head():
            client = self._client()
            client.head_object(Bucket=self.bucket, Key=key)

        try:
            await _run_in_executor(_head)
            return True
        except ClientError:
            return False

    async def get_object_metadata(self, key: str) -> Optional[dict]:
        """Get object metadata (size, last modified)."""
        def _head():
            client = self._client()
            return client.head_object(Bucket=self.bucket, Key=key)

        try:
            response = await _run_in_executor(_head)
            return {
                "size": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "content_type": response.get("ContentType", ""),
            }
        except ClientError:
            return None

    def normalize_key(self, path: str) -> str:
        """Normalize a path to a valid R2 key (no leading slash)."""
        return path.lstrip("/")

    def path_to_key(self, path: str) -> str:
        """Convert a panel path to an R2 key."""
        return self.normalize_key(path)

    def key_to_path(self, key: str) -> str:
        """Convert an R2 key to a panel path."""
        return "/" + key if not key.startswith("/") else key


# Singleton
r2_service = R2StorageService()
