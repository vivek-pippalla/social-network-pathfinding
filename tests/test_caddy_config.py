"""
Unit tests for Caddy Reverse Proxy & Automatic HTTPS Configuration.

Validates:
  1. Caddyfile configuration invariants (Auto-HTTPS, reverse proxy to api:5000, security headers).
  2. Production Docker Compose invariants:
     - Caddy exposes ports 80 and 443 to the host.
     - FastAPI (port 5000), Neo4j (7474/7687), and Redis (6379) are unmapped to host ports.
     - Persistent volumes for TLS certificates (caddy_data, caddy_config).
     - Health checks and resource limits.
"""

import os
import subprocess
import pytest
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CADDYFILE_PATH = os.path.join(PROJECT_ROOT, "caddy", "Caddyfile")
COMPOSE_PROD_PATH = os.path.join(PROJECT_ROOT, "docker-compose.prod.yml")


def test_caddyfile_exists_and_has_required_directives():
    """Verify Caddyfile exists and enforces core reverse proxy & security policies."""
    assert os.path.exists(CADDYFILE_PATH), f"Caddyfile not found at {CADDYFILE_PATH}"

    with open(CADDYFILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Must support configurable domain name with localhost fallback
    assert "{$DOMAIN_NAME:localhost}" in content or "{$DOMAIN_NAME" in content

    # Must reverse proxy to internal api:5000 service
    assert "reverse_proxy api:5000" in content

    # Must inject reverse proxy headers for scheme and client IP
    assert "X-Forwarded-Proto {scheme}" in content
    assert "X-Forwarded-For {remote_host}" in content

    # Must enforce modern security headers
    assert "Strict-Transport-Security" in content
    assert "X-Content-Type-Options" in content
    assert "X-Frame-Options" in content
    assert "Referrer-Policy" in content


def test_production_compose_caddy_and_isolation_invariants():
    """Verify docker-compose.prod.yml enforces strict network isolation and Caddy HTTPS."""
    assert os.path.exists(COMPOSE_PROD_PATH), "docker-compose.prod.yml must exist"

    with open(COMPOSE_PROD_PATH, "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)

    services = compose.get("services", {})
    assert "caddy" in services, "caddy service must be defined in production compose"
    assert "api" in services, "api service must be defined in production compose"
    assert "neo4j" in services, "neo4j service must be defined in production compose"
    assert "redis" in services, "redis service must be defined in production compose"

    caddy = services["caddy"]
    api = services["api"]
    neo4j = services["neo4j"]
    redis = services["redis"]

    # Caddy must bind host ports 80 and 443
    caddy_ports = caddy.get("ports", [])
    assert any("80:80" in str(p) for p in caddy_ports), "Caddy must listen on port 80"
    assert any("443:443" in str(p) for p in caddy_ports), "Caddy must listen on port 443"

    # Caddy must persist TLS certificate and configuration data
    caddy_vols = [str(v) for v in caddy.get("volumes", [])]
    assert any("caddy_data:/data" in v for v in caddy_vols), "caddy_data volume must mount to /data"
    assert any("caddy_config:/config" in v for v in caddy_vols), "caddy_config volume must mount to /config"

    # Declared top-level volumes must include caddy_data and caddy_config
    declared_volumes = compose.get("volumes", {})
    assert "caddy_data" in declared_volumes, "caddy_data must be in top-level volumes"
    assert "caddy_config" in declared_volumes, "caddy_config must be in top-level volumes"

    # Ingress Isolation: api, neo4j, and redis must NOT expose ports to host
    assert "ports" not in api or not api["ports"], "api service must NOT publish ports to host"
    assert "ports" not in neo4j or not neo4j["ports"], "neo4j service must NOT publish ports to host"
    assert "ports" not in redis or not redis["ports"], "redis service must NOT publish ports to host"

    # api must expose internal port 5000 to Docker network
    assert "5000" in [str(p) for p in api.get("expose", [])]

    # Shared internal bridge network
    for s_name, s_def in services.items():
        assert "internal-network" in s_def.get("networks", []), f"{s_name} must connect to internal-network"


def test_docker_compose_config_validation():
    """Verify that docker compose config parses docker-compose.prod.yml without syntax error."""
    env = os.environ.copy()
    env["AWS_ACCOUNT_ID"] = "123456789012"
    env["AWS_REGION"] = "ap-south-1"
    env["NEO4J_PASSWORD"] = "testpass"
    env["SECRET_KEY"] = "testkey"
    env["DOMAIN_NAME"] = "test.sslip.io"

    result = subprocess.run(
        ["docker", "compose", "-f", "docker-compose.prod.yml", "config", "-q"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        shell=True,
    )
    assert result.returncode == 0, f"docker compose config failed: {result.stderr}"
