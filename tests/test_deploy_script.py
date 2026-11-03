"""Behavioral tests for the local Compose deployment and rollback script."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "deploy" / "local" / "deploy.sh"
LOCAL_SCRIPTS = sorted((PROJECT_ROOT / "deploy" / "local").glob("*.sh"))
BASH = shutil.which("bash")


def _bash_is_usable():
    if BASH is None:
        return False
    try:
        result = subprocess.run(
            [BASH, "--version"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.mark.parametrize("script_path", LOCAL_SCRIPTS, ids=lambda path: path.name)
def test_local_scripts_are_valid_bash(script_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    result = subprocess.run(
        [BASH, "-n", str(script_path)], capture_output=True, text=True
    )

    assert result.returncode == 0, f"{script_path.name}: {result.stderr}"


@pytest.mark.parametrize(
    (
        "scenario",
        "previous_container",
        "curl_plan",
        "rollback_start_fails",
        "exit_code",
    ),
    [
        ("success", "container-old", "ok", False, 0),
        ("rollback", "container-old", "fail,ok", False, 1),
        ("rollback-fails", "container-old", "fail", True, 1),
        ("first-install-fails", "", "fail", False, 1),
    ],
)
def test_deploy_script_runs_expected_docker_and_health_actions(
    tmp_path,
    scenario,
    previous_container,
    curl_plan,
    rollback_start_fails,
    exit_code,
):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    _write_fake_executables(bin_dir, docker_log, curl_log)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{environment['PATH']}",
            "DOCKER_LOG": str(docker_log),
            "CURL_LOG": str(curl_log),
            "PREVIOUS_CONTAINER": previous_container,
            "PREVIOUS_IMAGE": "sha256:previous-image",
            "CURL_PLAN": curl_plan,
            "ROLLBACK_START_FAILS": "1" if rollback_start_fails else "0",
            "HEALTH_ATTEMPTS": "1",
            "HEALTH_INTERVAL_SECONDS": "0",
            "BASE_URL": "http://127.0.0.1:5000",
        }
    )
    result = subprocess.run(
        [BASH, str(SCRIPT_PATH)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == exit_code, result.stderr
    docker_actions = docker_log.read_text(encoding="utf-8").splitlines()
    curl_actions = curl_log.read_text(encoding="utf-8").splitlines()
    assert "compose build api" in docker_actions
    assert "compose up --detach --no-build" in docker_actions

    if scenario == "success":
        assert curl_actions == ["health"]
        assert not any("force-recreate" in action for action in docker_actions)
    elif scenario == "rollback":
        assert any(
            action.startswith("image tag sha256:previous-image ")
            for action in docker_actions
        )
        assert any("--force-recreate api" in action for action in docker_actions)
        assert curl_actions == ["health", "health"]
        assert "Previous API image was restored" in result.stdout
    elif scenario == "rollback-fails":
        assert any("--force-recreate api" in action for action in docker_actions)
        assert curl_actions == ["health"]
        assert "Rollback could not start" in result.stdout
    else:
        assert not any(action.startswith("image tag ") for action in docker_actions)
        assert "compose stop api" in docker_actions
        assert curl_actions == ["health"]


def test_bash_syntax_check_catches_the_legacy_if_do_error(tmp_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    source = SCRIPT_PATH.read_text(encoding="utf-8")
    mutated = source.replace("if wait_until_ready; then", "if wait_until_ready; do", 1)
    assert mutated != source
    broken_script = tmp_path / "broken-deploy.sh"
    broken_script.write_text(mutated, encoding="utf-8")

    result = subprocess.run(
        [BASH, "-n", str(broken_script)], capture_output=True, text=True
    )

    assert result.returncode != 0


def _write_fake_executables(bin_dir: Path, docker_log: Path, curl_log: Path) -> None:
    docker = bin_dir / "docker"
    docker.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os, sys\n"
        + "args = sys.argv[1:]\n"
        + "with open(os.environ['DOCKER_LOG'], 'a', encoding='utf-8') as f: f.write(' '.join(args) + '\\n')\n"
        + "if args == ['compose', 'ps', '--all', '--quiet', 'api']:\n"
        + "    print(os.environ.get('PREVIOUS_CONTAINER', ''))\n"
        + "elif args[:2] == ['inspect', '--format']:\n"
        + "    print(os.environ.get('PREVIOUS_IMAGE', ''))\n"
        + "elif args[:2] == ['compose', 'up'] and '--force-recreate' in args and os.environ.get('ROLLBACK_START_FAILS') == '1':\n"
        + "    sys.exit(17)\n",
        encoding="utf-8",
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os, sys\n"
        + "path = os.environ['CURL_LOG']\n"
        + "with open(path, 'a+', encoding='utf-8') as f:\n"
        + "    f.seek(0)\n"
        + "    number = len(f.readlines())\n"
        + "    f.write('health\\n')\n"
        + "plan = os.environ.get('CURL_PLAN', 'ok').split(',')\n"
        + "sys.exit(0 if plan[min(number, len(plan) - 1)] == 'ok' else 22)\n",
        encoding="utf-8",
    )
    for executable in (docker, curl):
        executable.chmod(0o755)
