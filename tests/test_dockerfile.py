"""Static Dockerfile checks; the built image is checked when Docker is available."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_image_uses_only_runtime_requirements_and_runs_as_non_root():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY requirements.txt ./requirements.txt" in dockerfile
    assert "-r requirements.txt" in dockerfile
    assert "requirements-dev.txt" not in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "WEB_CONCURRENCY=2" in dockerfile
    assert "--proxy-headers" in dockerfile
    assert "--forwarded-allow-ips" in dockerfile
    assert "http://127.0.0.1:5000/health" in dockerfile
    assert "COPY data/ ./data/" in dockerfile
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "backups/" in dockerignore
