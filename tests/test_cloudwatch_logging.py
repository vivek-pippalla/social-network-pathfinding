"""The optional integration loads AWS packages only when explicitly called."""

import builtins
import importlib


def test_core_logging_import_does_not_import_aws_packages(monkeypatch):
    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.split(".")[0] in {"boto3", "watchtower"}:
            raise AssertionError("optional AWS dependency imported by core")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    importlib.reload(importlib.import_module("app.core.logging"))
    importlib.reload(importlib.import_module("app.main"))


def test_cloudwatch_module_is_outside_core_and_imports_lazily():
    import inspect
    from optional_integrations import cloudwatch_logging

    source = inspect.getsource(cloudwatch_logging)
    assert "import boto3" in source
    assert "from watchtower import" in source
