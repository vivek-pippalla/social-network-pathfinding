"""The application and its normal startup do not require optional AWS packages."""

import os
import subprocess
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_app_starts_when_aws_packages_are_unavailable():
    script = """
import importlib.abc
import sys

class BlockAwsImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'boto3', 'botocore', 'watchtower'}:
            raise ModuleNotFoundError(f'blocked optional dependency: {fullname}')
        return None

sys.meta_path.insert(0, BlockAwsImports())

import app.main as main
import app.services.s3_service
import scripts.seed_data
main.get_driver = lambda: None
main.close_driver = lambda: None

from fastapi.testclient import TestClient
with TestClient(main.app) as client:
    assert client.get('/health').status_code == 200
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
