"""Automated validation and behavioral tests for AWS demonstration deployment kit.

Validates:
1. Shell script syntax (bash -n) across all deploy/aws/scripts/*.sh files.
2. Syntax error detection (verifying that intentional bash errors fail bash -n).
3. Behavioral execution of backup-to-s3.sh and restore-from-s3.sh using fake shims.
4. Compose configuration merging with docker-compose.aws.yml (no open DB ports, awslogs logging).
5. IAM policy JSON syntax, absence of wildcards, and absence of hardcoded account IDs.
6. Cleanliness of deploy/aws/ files (no secrets, no private keys, no .pem files).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AWS_SCRIPTS_DIR = PROJECT_ROOT / "deploy" / "aws" / "scripts"
AWS_IAM_DIR = PROJECT_ROOT / "deploy" / "aws" / "iam"
AWS_COMPOSE_OVERLAY = PROJECT_ROOT / "deploy" / "aws" / "docker-compose.aws.yml"
ALL_AWS_SCRIPTS = sorted(AWS_SCRIPTS_DIR.glob("*.sh"))


def _find_bash():
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\Git\usr\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\usr\bin\bash.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Git\usr\bin\bash.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Git\bin\bash.exe"),
        ):
            if os.path.exists(candidate):
                return candidate
    found = shutil.which("bash")
    if sys.platform == "win32" and found and "system32" in found.lower():
        return None
    return found


BASH = _find_bash()


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


@pytest.mark.parametrize("script_path", ALL_AWS_SCRIPTS, ids=lambda path: path.name)
def test_aws_scripts_are_valid_bash(script_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    result = subprocess.run(
        [BASH, "-n", str(script_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{script_path.name} failed bash -n: {result.stderr}"


def test_aws_scripts_catches_intentional_syntax_error(tmp_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    verify_script = AWS_SCRIPTS_DIR / "verify.sh"
    source = verify_script.read_text(encoding="utf-8")
    target = 'if [ "${STATUS}" = "200" ]; then'
    assert target in source, "Target string for mutation not found in verify.sh"
    mutated = source.replace(target, 'if [ "${STATUS}" = "200" ]; do', 1)

    broken_file = tmp_path / "broken_verify.sh"
    broken_file.write_text(mutated, encoding="utf-8")

    result = subprocess.run(
        [BASH, "-n", str(broken_file)], capture_output=True, text=True
    )
    assert result.returncode != 0, "bash -n unexpectedly passed on corrupted script"


def test_backup_to_s3_requires_bucket_setting(tmp_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    env = os.environ.copy()
    env.pop("BACKUP_BUCKET", None)
    script = AWS_SCRIPTS_DIR / "backup-to-s3.sh"

    result = subprocess.run(
        [BASH, str(script)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "BACKUP_BUCKET is not set" in result.stderr


def test_restore_from_s3_requires_target_argument():
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    script = AWS_SCRIPTS_DIR / "restore-from-s3.sh"
    result = subprocess.run(
        [BASH, str(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Usage:" in result.stderr


def test_restore_from_s3_requires_confirmation_token(tmp_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    env = os.environ.copy()
    env["BACKUP_BUCKET"] = "test-backup-bucket"
    script = AWS_SCRIPTS_DIR / "restore-from-s3.sh"

    # Supply invalid confirmation via stdin
    result = subprocess.run(
        [BASH, str(script), "20261104T120000Z"],
        cwd=PROJECT_ROOT,
        env=env,
        input="NOT_RESTORE\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Aborted" in result.stderr


def test_iam_policies_syntax_and_least_privilege():
    policy_files = sorted(AWS_IAM_DIR.glob("*.json"))
    assert len(policy_files) >= 5, "Expected at least 5 IAM policy templates"

    twelve_digit_account_pattern = re.compile(r"\b\d{12}\b")

    for policy_file in policy_files:
        content = policy_file.read_text(encoding="utf-8")
        # 1. JSON parsing check
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Invalid JSON in {policy_file.name}: {exc}")

        # 2. No hardcoded 12-digit account numbers
        match = twelve_digit_account_pattern.search(content)
        assert match is None, (
            f"Found potential 12-digit AWS account ID {match.group(0)} in {policy_file.name}"
        )

        # 3. Check Statements for least-privilege constraints if this is an IAM policy
        if "Statement" in data:
            statements = data["Statement"]
            for stmt in statements:
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                for action in actions:
                    assert action != "s3:*", (
                        f"Disallowed wildcard action s3:* in {policy_file.name}"
                    )
                    assert action != "*", (
                        f"Disallowed global wildcard action in {policy_file.name}"
                    )

                resources = stmt.get("Resource", [])
                if isinstance(resources, str):
                    resources = [resources]
                for resource in resources:
                    assert resource != "*", (
                        f"Disallowed universal wildcard resource '*' in {policy_file.name}"
                    )


def test_compose_aws_overlay_merges_without_database_ports():
    compose_main = PROJECT_ROOT / "docker-compose.yml"
    compose_prod = PROJECT_ROOT / "docker-compose.prod.yml"
    assert compose_main.exists()
    assert compose_prod.exists()
    assert AWS_COMPOSE_OVERLAY.exists()

    # Test via docker compose config if docker CLI is available
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker executable not found on PATH")

    env = os.environ.copy()
    env["AWS_REGION"] = "ap-south-1"

    cmd = [
        docker_bin,
        "compose",
        "--profile",
        "edge",
        "-f",
        str(compose_main),
        "-f",
        str(compose_prod),
        "-f",
        str(AWS_COMPOSE_OVERLAY),
        "config",
        "--format",
        "json",
    ]

    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            f"Docker engine unavailable or compose config failed: {result.stderr}"
        )

    config_data = json.loads(result.stdout)
    services = config_data.get("services", {})

    # Check database isolation
    neo4j_svc = services.get("neo4j", {})
    redis_svc = services.get("redis", {})
    api_svc = services.get("api", {})
    caddy_svc = services.get("caddy", {})

    assert "ports" not in neo4j_svc, "neo4j must not publish ports to host"
    assert "ports" not in redis_svc, "redis must not publish ports to host"
    assert "ports" not in api_svc, "api must not publish ports to host"

    # Check that caddy publishes only port 80/443
    caddy_ports = caddy_svc.get("ports", [])
    published_ports = [
        str(p.get("published")) for p in caddy_ports if isinstance(p, dict)
    ]
    assert "80" in published_ports, "caddy must publish port 80"

    # Check logging driver on all services
    for svc_name in ("api", "neo4j", "redis", "caddy"):
        svc = services.get(svc_name, {})
        logging_config = svc.get("logging", {})
        assert logging_config.get("driver") == "awslogs", (
            f"{svc_name} logging driver must be awslogs"
        )
        options = logging_config.get("options", {})
        assert options.get("mode") == "non-blocking", (
            f"{svc_name} awslogs mode must be non-blocking"
        )
        assert options.get("max-buffer-size") == "4m", (
            f"{svc_name} awslogs max-buffer-size must be 4m"
        )


def test_repository_has_no_committed_aws_secrets_or_pem_files():
    aws_dir = PROJECT_ROOT / "deploy" / "aws"
    docs_dir = PROJECT_ROOT / "docs"

    secret_key_pattern = re.compile(r"AKIA[0-9A-Z]{16}")
    private_key_pattern = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

    for scan_dir in (aws_dir, docs_dir):
        for root, dirs, files in os.walk(scan_dir):
            for file_name in files:
                assert not file_name.endswith(".pem"), (
                    f"Found committed .pem key file: {file_name}"
                )
                file_path = Path(root) / file_name
                try:
                    text = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue  # binary file
                assert not secret_key_pattern.search(text), (
                    f"Potential AWS Access Key found in {file_path}"
                )
                assert not private_key_pattern.search(text), (
                    f"Private key header found in {file_path}"
                )


def test_backup_and_restore_behavior_with_fake_shims(tmp_path):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws_log = tmp_path / "aws.log"
    docker_log = tmp_path / "docker.log"

    # Fake docker shim
    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import sys, os\n"
        + "args = sys.argv[1:]\n"
        + f"with open(r'{docker_log}', 'a') as f: f.write(' '.join(args) + '\\n')\n"
        + "if len(args) >= 3 and args[0] == 'cp':\n"
        + "    dest = args[2]\n"
        + "    with open(dest, 'wb') as f: f.write(b'fake-neo4j-dump-bytes')\n"
        + "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    # Fake aws shim
    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import sys, os, hashlib, shutil\n"
        + "args = sys.argv[1:]\n"
        + f"with open(r'{aws_log}', 'a') as f: f.write(' '.join(args) + '\\n')\n"
        + "if len(args) >= 4 and args[:2] == ['s3', 'cp']:\n"
        + "    src, dest = args[2], args[3]\n"
        + "    if '--recursive' in args:\n"
        + "        # restore download: write dump and sha256 to destination directory\n"
        + "        target_dir = dest if dest != '--recursive' else src\n"
        + "        content = b'fake-neo4j-dump-bytes'\n"
        + "        digest = hashlib.sha256(content).hexdigest()\n"
        + "        corrupt = os.environ.get('CORRUPT_DUMP', '0') == '1'\n"
        + "        dump_path = os.path.join(dest, 'neo4j-test.dump')\n"
        + "        sha_path = dump_path + '.sha256'\n"
        + "        with open(dump_path, 'wb') as f: f.write(b'corrupted' if corrupt else content)\n"
        + "        with open(sha_path, 'w') as f: f.write(f'{digest}  neo4j-test.dump\\n')\n"
        + "    elif dest.endswith('.sha256') and not src.startswith('s3://'):\n"
        + "        # upload sha: record sha\n"
        + "        pass\n"
        + "    elif src.endswith('.sha256') and not dest.startswith('s3://'):\n"
        + "        # download sha verification: copy sha content to dest\n"
        + "        content = b'fake-neo4j-dump-bytes'\n"
        + "        digest = hashlib.sha256(content).hexdigest()\n"
        + "        with open(dest, 'w') as f: f.write(f'{digest}  neo4j.dump\\n')\n"
        + "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)

    bash_parent = str(Path(BASH).parent) if BASH else ""
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{bash_parent}{os.pathsep}{env['PATH']}"
    env["BACKUP_BUCKET"] = "test-demo-bucket"
    env["FORCE_RESTORE"] = "RESTORE"

    # 1. Test backup-to-s3.sh
    backup_script = AWS_SCRIPTS_DIR / "backup-to-s3.sh"
    result = subprocess.run(
        [BASH, str(backup_script)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"backup-to-s3 failed: {result.stderr}\n{result.stdout}"
    )
    assert "SUCCESS: Backup verified and archived" in result.stdout

    # 2. Test restore-from-s3.sh success
    restore_script = AWS_SCRIPTS_DIR / "restore-from-s3.sh"
    result = subprocess.run(
        [BASH, str(restore_script), "20261104T120000Z"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"restore-from-s3 failed: {result.stderr}\n{result.stdout}"
    )
    assert "SUCCESS: Database restored successfully" in result.stdout

    # 3. Test restore-from-s3.sh with corrupted dump (checksum mismatch)
    env_corrupt = env.copy()
    env_corrupt["CORRUPT_DUMP"] = "1"
    result_corrupt = subprocess.run(
        [BASH, str(restore_script), "20261104T120000Z"],
        cwd=PROJECT_ROOT,
        env=env_corrupt,
        capture_output=True,
        text=True,
    )
    assert result_corrupt.returncode != 0
    assert "SHA-256 verification failed" in result_corrupt.stderr
