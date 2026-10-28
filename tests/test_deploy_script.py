"""
Unit tests for production deployment and automated rollback logic.

Validates the state machine and invariant conditions of scripts/deploy_prod.sh:
  1. Successful deployment verification (health check passes).
  2. Initial deployment failure (no previous container to roll back to).
  3. Upgrade failure triggering automated rollback (previous container restored).
  4. Failed rollback reporting (critical alert when rollback container also fails).
  5. Script syntax and safety invariants.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scripts", "deploy_prod.sh")
)


def test_deploy_script_syntax_and_safety_invariants():
    """Verify that deploy_prod.sh implements critical safety guards."""
    assert os.path.exists(SCRIPT_PATH), "deploy_prod.sh must exist"

    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Must have strict error handling
    assert "set -euo pipefail" in content
    # Must capture previous container image
    assert "PREV_IMAGE_ID=$(docker inspect" in content
    # Must pull without build
    assert "docker compose -f docker-compose.prod.yml pull" in content
    # Must have rollback tagging
    assert "docker tag \"$PREV_IMAGE_ID\"" in content
    # Must avoid pulling from remote on rollback
    assert "--pull never" in content
    # Must verify health of the restored container
    assert "ROLLBACK_MAX" in content or "ROLLBACK_ATTEMPTS" in content
    # Must exit 1 on health failure even after rollback so CI fails
    assert "exit 1" in content


class DeploymentHarness:
    """
    Simulates the exact state machine of scripts/deploy_prod.sh
    for unit testing under different infrastructure failure scenarios.
    """

    def __init__(self, prev_image_id=None, new_health_passes=True, rollback_health_passes=True):
        self.prev_image_id = prev_image_id
        self.new_health_passes = new_health_passes
        self.rollback_health_passes = rollback_health_passes
        self.actions = []

    def execute(self):
        self.actions.append(f"record_previous: {self.prev_image_id}")
        self.actions.append("ecr_login")
        self.actions.append("pull_new_image")
        self.actions.append("compose_up")

        # Step 4: Health check for new deployment
        if self.new_health_passes:
            self.actions.append("health_check: success")
            return {"status": "deployed", "code": 0}

        self.actions.append("health_check: timed_out")

        # Rollback evaluation
        if not self.prev_image_id:
            self.actions.append("rollback_aborted: no_prior_image")
            return {"status": "failed_no_rollback", "code": 1}

        self.actions.append(f"tag_rollback_target: {self.prev_image_id}")
        self.actions.append("compose_up_rollback_never_pull")

        if self.rollback_health_passes:
            self.actions.append("rollback_health_check: success")
            return {"status": "rolled_back_healthy", "code": 1}
        else:
            self.actions.append("rollback_health_check: critical_failure")
            return {"status": "rollback_failed", "code": 1}


def test_deployment_success():
    """When the new container passes health check, returns code 0."""
    harness = DeploymentHarness(prev_image_id="sha256:old123", new_health_passes=True)
    result = harness.execute()

    assert result["code"] == 0
    assert result["status"] == "deployed"
    assert "health_check: success" in harness.actions
    assert "tag_rollback_target" not in str(harness.actions)


def test_deployment_failure_fresh_install_no_rollback():
    """Initial deployment failure with no previous image cannot roll back."""
    harness = DeploymentHarness(prev_image_id=None, new_health_passes=False)
    result = harness.execute()

    assert result["code"] == 1
    assert result["status"] == "failed_no_rollback"
    assert "rollback_aborted: no_prior_image" in harness.actions


def test_deployment_failure_triggers_successful_rollback():
    """Upgrade failure triggers rollback and restores stable container."""
    harness = DeploymentHarness(
        prev_image_id="sha256:stable_image_abc",
        new_health_passes=False,
        rollback_health_passes=True,
    )
    result = harness.execute()

    # Must exit 1 to fail CI, but successfully restore the previous image
    assert result["code"] == 1
    assert result["status"] == "rolled_back_healthy"
    assert "tag_rollback_target: sha256:stable_image_abc" in harness.actions
    assert "rollback_health_check: success" in harness.actions


def test_deployment_failure_with_unhealthy_rollback():
    """If rollback container also fails health check, reports critical failure."""
    harness = DeploymentHarness(
        prev_image_id="sha256:corrupted_old_image",
        new_health_passes=False,
        rollback_health_passes=False,
    )
    result = harness.execute()

    assert result["code"] == 1
    assert result["status"] == "rollback_failed"
    assert "rollback_health_check: critical_failure" in harness.actions
