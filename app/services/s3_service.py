"""
S3 Dataset Ingestion and Validation Service.

Handles dataset retrieval from Amazon S3 for production,
with automatic local/URL fallback for development.
Includes data validation to filter malformed edge records and report metrics.
"""

import gzip
import logging
import os
import urllib.request
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError

from app.core.config import settings

logger = logging.getLogger(__name__)


def download_from_s3(bucket: str, key: str, target_path: str, s3_client=None) -> bool:
    """Download dataset object from private S3 bucket."""
    client = s3_client or boto3.client("s3", region_name=settings.AWS_REGION)
    logger.info(f"Downloading s3://{bucket}/{key} -> {target_path}")
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        client.download_file(bucket, key, target_path)
        return os.path.exists(target_path) and os.path.getsize(target_path) > 0
    except (ClientError, BotoCoreError, NoCredentialsError) as e:
        logger.error(f"S3 download failed (s3://{bucket}/{key}): {e}")
        return False


def ensure_dataset(
    target_path: str,
    bucket: Optional[str] = None,
    key: Optional[str] = None,
    fallback_url: Optional[str] = None,
    s3_client=None,
    require_s3: bool = False,
) -> Tuple[str, str]:
    """
    Ensure the dataset file exists locally:
      1. Use local cache if already present.
      2. If bucket is configured, download from S3 (raises error if S3 required).
      3. Fallback to public URL for local development.

    Returns:
      (file_path: str, source_used: str)
    """
    # 1. Local cache hit
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        logger.info(f"Using existing dataset cache at: {target_path}")
        return target_path, "local_cache"

    # 2. S3 ingestion (production path)
    bucket_name = bucket or settings.AWS_S3_BUCKET
    key_name = key or settings.AWS_S3_DATASET_KEY

    if bucket_name:
        success = download_from_s3(bucket_name, key_name, target_path, s3_client=s3_client)
        if success:
            logger.info(f"Successfully retrieved dataset from S3: {target_path}")
            return target_path, "s3"
        if require_s3:
            raise RuntimeError(f"Required S3 download failed for s3://{bucket_name}/{key_name}")
        logger.warning("S3 download failed. Attempting URL fallback for local development...")

    # 3. Fallback URL (development path)
    if fallback_url:
        logger.info(f"Downloading from fallback URL: {fallback_url}")
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        urllib.request.urlretrieve(fallback_url, target_path)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            return target_path, "url"

    raise RuntimeError(f"Unable to obtain dataset at: {target_path}")


def parse_and_validate_edges(file_path: str) -> dict:
    """
    Parse and validate the dataset edge list (.gz or plain text).
    Filters comments and malformed records, returning clean edges and stats.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    open_fn = gzip.open if file_path.endswith(".gz") else open
    valid_edges = []
    unique_users = set()
    total_lines = 0
    rejected_records = 0

    with open_fn(file_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            total_lines += 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            parts = stripped.split()
            if len(parts) == 2 and parts[0] and parts[1]:
                valid_edges.append((parts[0], parts[1]))
                unique_users.add(parts[0])
                unique_users.add(parts[1])
            else:
                rejected_records += 1

    return {
        "valid_edges": valid_edges,
        "unique_users": list(unique_users),
        "stats": {
            "total_lines": total_lines,
            "valid_records": len(valid_edges),
            "rejected_records": rejected_records,
            "unique_users": len(unique_users),
        },
    }
