"""
Unit tests for S3 dataset ingestion, fallback, and validation.

All AWS S3 and network interactions are mocked to guarantee
offline test runs without live AWS infrastructure.
"""

import gzip
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from app.services.s3_service import (
    download_from_s3,
    ensure_dataset,
    parse_and_validate_edges,
)


@pytest.fixture
def sample_edge_file():
    """Create a temporary edge file with valid, comment, and malformed rows."""
    content = (
        "# SNAP Facebook Dataset Sample\n"
        "0 1\n"
        "0 2\n"
        "\n"
        "1 2\n"
        "bad_line_single_token\n"
        "2 3\n"
        "# Another comment\n"
        "3 4 5"
    )
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def sample_gzipped_edge_file():
    """Create a temporary gzipped edge file."""
    content = b"0 1\n0 2\n1 3\n"
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".txt.gz") as f:
        with gzip.GzipFile(fileobj=f, mode="wb") as gz:
            gz.write(content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_parse_and_validate_edges(sample_edge_file):
    """Ensure records are correctly parsed and malformed rows counted as rejected."""
    result = parse_and_validate_edges(sample_edge_file)
    stats = result["stats"]

    assert stats["total_lines"] == 9
    assert stats["valid_records"] == 4
    assert stats["rejected_records"] == 2
    assert stats["unique_users"] == 4
    assert ("0", "1") in result["valid_edges"]
    assert ("2", "3") in result["valid_edges"]


def test_parse_and_validate_gzipped(sample_gzipped_edge_file):
    """Ensure gzipped files are transparently uncompressed and parsed."""
    result = parse_and_validate_edges(sample_gzipped_edge_file)
    assert result["stats"]["valid_records"] == 3
    assert ("1", "3") in result["valid_edges"]


def test_download_from_s3_success():
    """Test successful S3 download with mocked client."""
    mock_s3 = MagicMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "dataset.txt.gz")

        def fake_download(b, k, filename):
            with open(filename, "w") as f:
                f.write("mocked S3 content")

        mock_s3.download_file.side_effect = fake_download

        success = download_from_s3(
            bucket="prod-bucket",
            key="datasets/facebook.txt.gz",
            target_path=target,
            s3_client=mock_s3,
        )

        assert success is True
        mock_s3.download_file.assert_called_once_with(
            "prod-bucket", "datasets/facebook.txt.gz", target
        )
        assert os.path.exists(target)


def test_download_from_s3_client_error():
    """Test S3 download handling of AWS 404 ClientError gracefully."""
    mock_s3 = MagicMock()
    err_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_s3.download_file.side_effect = ClientError(err_response, "GetObject")

    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "missing.txt.gz")
        success = download_from_s3("bucket", "key", target, s3_client=mock_s3)
        assert success is False


def test_download_from_s3_no_credentials():
    """Test S3 download behavior when no AWS credentials exist (local dev)."""
    mock_s3 = MagicMock()
    mock_s3.download_file.side_effect = NoCredentialsError()

    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "test.txt.gz")
        success = download_from_s3("bucket", "key", target, s3_client=mock_s3)
        assert success is False


def test_ensure_dataset_local_cache():
    """Existing local file should be used directly when non-empty."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("existing cache content")
        temp_path = f.name

    try:
        path, source = ensure_dataset(target_path=temp_path)
        assert path == temp_path
        assert source == "local_cache"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@patch("app.services.s3_service.download_from_s3", return_value=True)
def test_ensure_dataset_downloads_from_s3(mock_s3_download):
    """When S3 bucket is configured and file not cached, download from S3."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "target.txt.gz")
        path, source = ensure_dataset(
            target_path=target,
            bucket="prod-bucket",
            key="dataset.gz",
        )
        assert source == "s3"
        mock_s3_download.assert_called_once()


@patch("app.services.s3_service.download_from_s3", return_value=False)
def test_ensure_dataset_production_failure_raises_error(mock_s3_download):
    """When require_s3=True (production mode), S3 failure must raise RuntimeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "target.txt.gz")
        with pytest.raises(RuntimeError, match="Required S3 download failed"):
            ensure_dataset(
                target_path=target,
                bucket="prod-bucket",
                key="dataset.gz",
                require_s3=True,
            )


@patch("app.services.s3_service.download_from_s3", return_value=False)
@patch("urllib.request.urlretrieve")
def test_ensure_dataset_falls_back_to_url_in_dev(mock_urlretrieve, mock_s3_download):
    """In development (require_s3=False), S3 failure falls back to URL without crashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "target.txt.gz")

        def fake_urlretrieve(url, filename):
            with open(filename, "w") as f:
                f.write("url content")

        mock_urlretrieve.side_effect = fake_urlretrieve

        path, source = ensure_dataset(
            target_path=target,
            bucket="dev-bucket",
            key="dataset.gz",
            fallback_url="https://snap.stanford.edu/test.gz",
            require_s3=False,
        )
        assert source == "url"
        mock_s3_download.assert_called_once()
        mock_urlretrieve.assert_called_once()
