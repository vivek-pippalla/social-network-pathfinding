from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
SHA_REF = re.compile(r"^[0-9a-f]{40}$")


def _load(name: str) -> dict:
    return yaml.load(
        (WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )


def test_all_external_actions_are_pinned_to_full_commit_shas():
    for workflow in WORKFLOWS.glob("*.yml"):
        document = yaml.load(
            workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
        for job in document["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    assert SHA_REF.fullmatch(step["uses"].rsplit("@", 1)[1]), (
                        workflow.name,
                        step["uses"],
                    )


def test_ci_has_separate_required_jobs_and_least_privilege_permissions():
    workflow = _load("ci.yml")

    assert set(workflow["jobs"]) == {
        "lint",
        "unit",
        "integration",
        "contract",
        "e2e",
        "security",
        "image",
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert "cancel-in-progress" in workflow["concurrency"]
    integration = workflow["jobs"]["integration"]
    assert "neo4j" in integration["services"]
    assert "redis" in integration["services"]
    assert integration["env"]["REQUIRE_INTEGRATION"] == "1"


def test_optional_aws_packaging_is_manual_and_oidc_is_job_scoped():
    workflow = _load("deploy-aws.yml")

    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "aws-demo-package",
        "cancel-in-progress": "false",
    }
    assert workflow["jobs"]["package-release"]["permissions"] == {
        "contents": "read",
        "id-token": "write",
    }
    assert (
        workflow["jobs"]["package-release"]["if"]
        == "${{ vars.AWS_DEMO_ENABLED == 'true' }}"
    )
    content = (WORKFLOWS / "deploy-aws.yml").read_text(encoding="utf-8")
    assert "AWS_ACCESS_KEY_ID" not in content
    assert "AWS_SECRET_ACCESS_KEY" not in content
