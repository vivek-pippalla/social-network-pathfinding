"""Checks for Caddy ingress and the production Compose boundary."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CADDYFILE_PATH = PROJECT_ROOT / "caddy" / "Caddyfile"


def test_caddyfile_uses_configurable_site_and_blocks_metrics():
    content = CADDYFILE_PATH.read_text(encoding="utf-8")

    assert "{$SITE_ADDRESS:localhost}" in content
    assert "reverse_proxy api:5000" in content
    assert "@metrics path /metrics /metrics/*" in content
    assert "respond @metrics 404" in content
    assert "X-Forwarded-Proto {scheme}" in content
    assert "X-Forwarded-For {remote_host}" in content
    assert "Strict-Transport-Security" in content
    assert "X-Content-Type-Options" in content
    assert "X-Frame-Options" in content
    assert "Referrer-Policy" in content


def test_development_compose_binds_published_ports_to_loopback(tmp_path):
    config = _compose_config(
        tmp_path,
        profile_args=[],
        files=["docker-compose.yml", "docker-compose.override.yml"],
    )
    services = _enabled_services(config, set())

    assert set(("api", "neo4j", "redis")).issubset(services)
    assert _published_ports(services["api"]) == {"127.0.0.1:5000"}
    assert _published_ports(services["neo4j"]) == {
        "127.0.0.1:7474",
        "127.0.0.1:7687",
    }
    assert _published_ports(services["redis"]) == {"127.0.0.1:6379"}
    assert "--reload" in services["api"]["command"]
    _assert_passwords_are_explicit(services)


def test_monitoring_profile_binds_only_monitoring_ports_to_loopback(tmp_path):
    config = _compose_config(
        tmp_path,
        profile_args=["--profile", "monitoring"],
        files=["docker-compose.yml", "docker-compose.override.yml"],
    )
    services = _enabled_services(config, {"monitoring"})

    assert {"prometheus", "grafana"}.issubset(services)
    assert _published_ports(services["prometheus"]) == {"127.0.0.1:9090"}
    assert _published_ports(services["grafana"]) == {"127.0.0.1:3000"}
    _assert_passwords_are_explicit(services)


def test_prod_like_compose_publishes_only_caddy_and_disables_docs(tmp_path):
    config = _compose_config(
        tmp_path,
        profile_args=["--profile", "edge"],
        files=["docker-compose.yml", "docker-compose.prod.yml"],
    )
    services = _enabled_services(config, {"edge"})

    assert set(("api", "neo4j", "redis", "caddy")).issubset(services)
    assert _published_ports(services["api"]) == set()
    assert _published_ports(services["neo4j"]) == set()
    assert _published_ports(services["redis"]) == set()
    assert _published_ports(services["caddy"]) == {"80:80", "443:443"}
    assert services["api"]["environment"]["ENABLE_DOCS"] == "false"
    assert services["api"]["environment"]["APP_ENV"] == "prod"
    assert "172.29.0.0/24" in services["api"]["environment"]["FORWARDED_ALLOW_IPS"]
    _assert_passwords_are_explicit(services)


def test_prod_like_monitoring_profile_publishes_only_edge_and_local_monitoring(
    tmp_path,
):
    config = _compose_config(
        tmp_path,
        profile_args=["--profile", "edge", "--profile", "monitoring"],
        files=["docker-compose.yml", "docker-compose.prod.yml"],
    )
    services = _enabled_services(config, {"edge", "monitoring"})

    assert _published_ports(services["api"]) == set()
    assert _published_ports(services["neo4j"]) == set()
    assert _published_ports(services["redis"]) == set()
    assert _published_ports(services["caddy"]) == {"80:80", "443:443"}
    assert _published_ports(services["prometheus"]) == {"127.0.0.1:9090"}
    assert _published_ports(services["grafana"]) == {"127.0.0.1:3000"}
    _assert_passwords_are_explicit(services)


def _compose_config(tmp_path, *, profile_args, files=None):
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not installed; Compose model was not validated")

    docker_config = tmp_path / "docker-config"
    docker_config.mkdir(exist_ok=True)
    app_env_file = tmp_path / "app.env"
    app_env_file.write_text(
        "APP_ENV=dev\n"
        "NEO4J_USER=neo4j\n"
        "NEO4J_PASSWORD=phase11-test-neo4j-password\n"
        "REDIS_PASSWORD=phase11-test-redis-password\n"
        "SECRET_KEY=phase11-test-secret-value-at-least-32-chars\n"
        "ENABLE_DOCS=true\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.update(
        {
            "DOCKER_CONFIG": str(docker_config),
            "COMPOSE_DISABLE_ENV_FILE": "1",
            "APP_ENV_FILE": str(app_env_file),
            "NEO4J_PASSWORD": "phase11-test-neo4j-password",
            "REDIS_PASSWORD": "phase11-test-redis-password",
            "SECRET_KEY": "phase11-test-secret-value-at-least-32-chars",
            "API_IMAGE": "phase11-test-api:local",
            "GRAFANA_ADMIN_USER": "phase11-test-grafana-user",
            "GRAFANA_ADMIN_PASSWORD": "phase11-test-grafana-password",
            "SITE_ADDRESS": ":80",
            "TRUSTED_PROXY_ADDRESSES": (
                "172.29.0.0/24" if "edge" in profile_args else "127.0.0.1,::1"
            ),
            "EDGE_NETWORK_SUBNET": "172.29.0.0/24",
            "NEO4J_HEAP_MAX": "1G",
            "NEO4J_PAGECACHE": "512M",
        }
    )
    args = ["docker", "compose"]
    for compose_file in files or ["docker-compose.yml"]:
        args.extend(["-f", compose_file])
    args.extend(profile_args)
    args.extend(["config", "--format", "json"])
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, (
        "docker compose config failed; details were suppressed"
    )
    return json.loads(result.stdout)


def _enabled_services(config, active_profiles):
    return {
        name: service
        for name, service in config["services"].items()
        if not service.get("profiles")
        or active_profiles.intersection(service["profiles"])
    }


def _published_ports(service):
    published = set()
    for port in service.get("ports", []):
        host_port = str(port["published"])
        host_ip = port.get("host_ip")
        if host_ip:
            published.add(f"{host_ip}:{host_port}")
        else:
            published.add(f"{host_port}:{port['target']}")
    return published


def _assert_passwords_are_explicit(services):
    assert all(
        service.get("restart") == "unless-stopped" for service in services.values()
    )
    neo4j_auth = services["neo4j"]["environment"]["NEO4J_AUTH"]
    neo4j_environment = services["neo4j"]["environment"]
    assert neo4j_environment["NEO4J_server_memory_heap_initial__size"] == "512M"
    assert neo4j_environment["NEO4J_server_memory_heap_max__size"] == "1G"
    assert neo4j_environment["NEO4J_server_memory_pagecache_size"] == "512M"
    assert (
        services["api"]["environment"]["REDIS_URL"]
        == "redis://:phase11-test-redis-password@redis:6379/0"
    )
    assert neo4j_auth == "neo4j/phase11-test-neo4j-password"
    redis_command = " ".join(services["redis"]["command"])
    assert "phase11-test-redis-password" in redis_command
    assert "volatile-lru" in redis_command
    assert "allkeys-lru" not in redis_command
    assert "--appendonly no" in redis_command
    assert "password123" not in neo4j_auth.lower()
    assert "admin/admin" not in redis_command.lower()
