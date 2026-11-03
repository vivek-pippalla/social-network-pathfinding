import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_monitoring_profile_is_local_only_and_grafana_has_no_default_credentials():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    prometheus = compose["services"]["prometheus"]
    grafana = compose["services"]["grafana"]
    api = compose["services"]["api"]

    assert "monitoring" in prometheus["profiles"]
    assert "monitoring" in grafana["profiles"]
    assert prometheus["ports"] == ["127.0.0.1:9090:9090"]
    assert grafana["ports"] == ["127.0.0.1:3000:3000"]
    assert api["ports"] == ["127.0.0.1:5000:5000"]
    assert grafana["environment"]["GF_SECURITY_ADMIN_USER"] == "${GRAFANA_ADMIN_USER:-}"
    assert (
        grafana["environment"]["GF_SECURITY_ADMIN_PASSWORD"]
        == "${GRAFANA_ADMIN_PASSWORD:-}"
    )
    assert "admin" not in grafana["environment"]["GF_SECURITY_ADMIN_USER"]
    assert "admin" not in grafana["environment"]["GF_SECURITY_ADMIN_PASSWORD"]
    guard = grafana["command"][0]
    assert "test -n" in guard
    assert '!= "replace-with-a-grafana-admin-user"' in guard
    assert '!= "replace-with-a-unique-grafana-password"' in guard


def test_prometheus_scrapes_api_and_dashboard_exposes_required_panels():
    prometheus = yaml.safe_load(
        (ROOT / "monitoring" / "prometheus.yml").read_text(encoding="utf-8")
    )
    dashboard = json.loads(
        (
            ROOT / "monitoring" / "grafana" / "dashboards" / "sample-dashboard.json"
        ).read_text(encoding="utf-8")
    )["dashboard"]

    scrape = next(
        item
        for item in prometheus["scrape_configs"]
        if item["job_name"] == "social-network-api"
    )
    assert scrape["metrics_path"] == "/metrics"
    assert scrape["static_configs"][0]["targets"] == ["api:5000"]
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert titles == {
        "Request rate",
        "HTTP error rate",
        "HTTP latency percentiles",
        "Path cache hit ratio",
        "Neo4j query latency p95 by operation",
    }
    expressions = " ".join(
        target["expr"] for panel in dashboard["panels"] for target in panel["targets"]
    )
    assert "histogram_quantile(0.50" in expressions
    assert "histogram_quantile(0.95" in expressions
    assert "histogram_quantile(0.99" in expressions
    assert "neo4j_query_duration_seconds_bucket" in expressions
