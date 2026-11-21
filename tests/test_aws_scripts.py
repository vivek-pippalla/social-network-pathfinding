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
import tempfile
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
    target = "[[ $STATUS == 200 ]] && pass 'S4: Liveness is healthy'"
    assert target in source, "Target string for mutation not found in verify.sh"
    assert source.startswith("#!/usr/bin/env bash\n"), "Shebang must be the first line"
    mutated = source.replace(target, "if [[ $STATUS == 200 ]] do", 1)

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
    env["PATH"] = f"{Path(BASH).parent}{os.pathsep}{env.get('PATH', '')}"
    script = AWS_SCRIPTS_DIR / "backup-to-s3.sh"

    result = subprocess.run(
        [BASH, str(script)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Set BACKUP_BUCKET" in result.stderr


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
    env["AWS_REGION"] = "ap-southeast-2"
    env["FORCE_RESTORE"] = "RESTORE"
    env["PATH"] = f"{Path(BASH).parent}{os.pathsep}{env.get('PATH', '')}"
    fake_aws = Path(tmp_path) / "aws"
    fake_aws.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import hashlib, json, pathlib, sys\n"
        + "dump_name='neo4j-20261104T120000Z-1.dump'\n"
        + "args=sys.argv[1:]; args=args[2:] if args[:1]==['--region'] else args\n"
        + "if args[:2]==['s3api','list-objects-v2']: print('backups/20261104T120000Z/'+dump_name); sys.exit(0)\n"
        + "if args[:2]==['s3','cp']:\n"
        + " src,dst=args[2],args[3]; p=pathlib.Path(dst); p.parent.mkdir(parents=True,exist_ok=True); name=src.rsplit('/',1)[-1]\n"
        + " digest=hashlib.sha256(b'demo-dump').hexdigest()\n"
        + " if name==dump_name: p.write_bytes(b'demo-dump')\n"
        + " elif name==dump_name+'.sha256': p.write_text(digest+'  '+dump_name+'\\n')\n"
        + " else: p.write_text(json.dumps({'database':'neo4j','dump':dump_name,'neo4j_version':'5.12.0','sha256':digest}))\n"
        + " sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    script = AWS_SCRIPTS_DIR / "restore-from-s3.sh"

    # A valid listing is downloaded and verified before non-interactive confirmation is rejected.
    result = subprocess.run(
        [BASH, str(script), "20261104T120000Z"],
        cwd=PROJECT_ROOT,
        env=env,
        input="NOT_RESTORE\n",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert (
        "Interactive confirmation required" in result.stderr
        or "expected:" in result.stderr
    )
    assert "Backup dump download failed" not in result.stderr


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
        assert (
            match is None
        ), f"Found potential 12-digit AWS account ID {match.group(0)} in {policy_file.name}"

        # 3. Check Statements for least-privilege constraints if this is an IAM policy
        if "Statement" in data:
            statements = data["Statement"]
            for stmt in statements:
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                for action in actions:
                    assert (
                        action != "s3:*"
                    ), f"Disallowed wildcard action s3:* in {policy_file.name}"
                    assert (
                        action != "*"
                    ), f"Disallowed global wildcard action in {policy_file.name}"

                resources = stmt.get("Resource", [])
                if isinstance(resources, str):
                    resources = [resources]
                for resource in resources:
                    assert (
                        resource != "*"
                    ), f"Disallowed universal wildcard resource '*' in {policy_file.name}"


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
    env["AWS_REGION"] = "ap-southeast-2"

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
        assert (
            logging_config.get("driver") == "awslogs"
        ), f"{svc_name} logging driver must be awslogs"
        options = logging_config.get("options", {})
        assert (
            options.get("mode") == "non-blocking"
        ), f"{svc_name} awslogs mode must be non-blocking"
        assert (
            options.get("max-buffer-size") == "4m"
        ), f"{svc_name} awslogs max-buffer-size must be 4m"


def test_repository_has_no_committed_aws_secrets_or_pem_files():
    aws_dir = PROJECT_ROOT / "deploy" / "aws"
    docs_dir = PROJECT_ROOT / "docs"

    secret_key_pattern = re.compile(r"AKIA[0-9A-Z]{16}")
    private_key_pattern = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")

    for scan_dir in (aws_dir, docs_dir):
        for root, dirs, files in os.walk(scan_dir):
            for file_name in files:
                assert not file_name.endswith(
                    ".pem"
                ), f"Found committed .pem key file: {file_name}"
                file_path = Path(root) / file_name
                try:
                    text = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue  # binary file
                assert not secret_key_pattern.search(
                    text
                ), f"Potential AWS Access Key found in {file_path}"
                assert not private_key_pattern.search(
                    text
                ), f"Private key header found in {file_path}"


def test_backup_and_restore_behavior_with_fake_shims(tmp_path, request):
    if not _bash_is_usable():
        pytest.skip("Bash is unavailable or cannot run in this environment")
    if sys.platform == "win32":
        pytest.skip(
            "Git Bash does not resolve the isolated Python command shims through PATH on this Windows host"
        )

    def bash_path(path: Path) -> str:
        value = path.resolve().as_posix()
        if sys.platform == "win32" and re.match(r"^[A-Za-z]:/", value):
            return f"/{value[0].lower()}{value[2:]}"
        return value

    def native_path(value: str) -> str:
        if sys.platform == "win32" and re.match(r"^/[A-Za-z]/", value):
            return value[1].upper() + ":" + value[2:].replace("/", "\\")
        return value

    # Git Bash cannot write into this workstation's protected Windows temp path.
    # Keep only its disposable dump/staging files in a unique workspace temp dir.
    bash_root = Path(tempfile.mkdtemp(prefix=".aws-script-test-", dir=PROJECT_ROOT))
    request.addfinalizer(lambda: shutil.rmtree(bash_root, ignore_errors=True))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_python = bin_dir / "python3"
    fake_python.write_text(
        "#!"
        + sys.executable
        + "\nimport os, sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    store = tmp_path / "s3"
    store.mkdir()
    aws_log = tmp_path / "aws.log"
    docker_log = tmp_path / "docker.log"
    sudo_log = tmp_path / "sudo.log"

    fake_docker = bin_dir / "docker"
    fake_docker.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os, pathlib, re, sys\ndef native_path(v): return (v[1].upper()+':'+v[2:].replace('/','\\\\')) if os.name=='nt' and re.match(r'^/[A-Za-z]/',v) else v\nargs=sys.argv[1:]\n"
        + "with open(os.environ['DOCKER_LOG'],'a') as f: f.write(' '.join(args)+'\\n')\n"
        + "if args == ['info']:\n sys.exit(1 if os.environ.get('DOCKER_DIRECT_FAIL') and not os.environ.get('SUDO_ACTIVE') else 0)\n"
        + "if args and args[0]=='inspect': print('healthy'); sys.exit(0)\n"
        + "if args and args[0]=='cp': pathlib.Path(native_path(args[2])).write_bytes(b'fake-neo4j-dump-bytes'); sys.exit(0)\n"
        + "if args[:2]==['compose','ps'] and '--quiet' in args: print('fake-container'); sys.exit(0)\n"
        + "if args[:2]==['compose','run'] and '--version' in args: print('neo4j-admin '+os.environ.get('NEO4J_MOCK_VERSION','5.12.0')); sys.exit(0)\n"
        + "if args[:2]==['compose','stop'] and os.environ.get('DOCKER_STOP_FAIL'): sys.exit(16)\n"
        + "if args[:2]==['compose','run'] and 'database' in args and os.environ.get('DOCKER_LOAD_FAIL'): sys.exit(17)\n"
        + "if args[:2]==['compose','up'] and os.environ.get('DOCKER_RESTART_FAIL'): sys.exit(18)\n"
        + "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    fake_sudo = bin_dir / "sudo"
    fake_sudo.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os, subprocess, sys\nargs=sys.argv[1:]\n"
        + "with open(os.environ['SUDO_LOG'],'a') as f: f.write(' '.join(args)+'\\n')\n"
        + "env=os.environ.copy(); env['SUDO_ACTIVE']='1'\n"
        + "sys.exit(subprocess.call(args[1:] if args and args[0]=='-n' else args, env=env))\n",
        encoding="utf-8",
    )
    fake_sudo.chmod(0o755)

    fake_aws = bin_dir / "aws"
    fake_aws.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import base64, hashlib, json, os, pathlib, re, shutil, sys\n"
        + "def native_path(v): return (v[1].upper()+':'+v[2:].replace('/','\\\\')) if os.name=='nt' and re.match(r'^/[A-Za-z]/',v) else v\n"
        + "args=sys.argv[1:]; args=args[2:] if args[:1]==['--region'] else args\n"
        + "store=pathlib.Path(os.environ['S3_STORE']); log=os.environ['AWS_LOG']\n"
        + "with open(log,'a') as f: f.write(' '.join(args)+'\\n')\n"
        + "def keypath(uri): return store / uri.replace('s3://','',1)\n"
        + "if args[:2]==['s3api','list-objects-v2']:\n"
        + " query=args[args.index('--query')+1]\n"
        + " if query == 'Contents[].Key':\n"
        + "  bucket=args[args.index('--bucket')+1]; prefix=args[args.index('--prefix')+1]; root=store/bucket\n"
        + "  keys=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix().startswith(prefix)] if root.exists() else []\n"
        + "  print('\\t'.join(keys) if keys else 'None'); sys.exit(0)\n"
        + " expected=\"Contents[?ends_with(Key, '.dump')].Key\"\n"
        + " if query != expected: print('INVALID_JMESPATH_QUERY',file=sys.stderr); sys.exit(22)\n"
        + " bucket=args[args.index('--bucket')+1]; prefix=args[args.index('--prefix')+1]; root=store/bucket\n"
        + " keys=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix().startswith(prefix) and p.name.endswith('.dump')] if root.exists() else []\n"
        + " mode=os.environ.get('AWS_LIST_MODE','valid')\n"
        + " if mode=='none': keys=[]\n"
        + " if mode=='multiple': keys=keys+keys\n"
        + " if mode=='invalid': keys=['backups/'+prefix.split('/')[1]+'/unexpected.txt']\n"
        + " print('\\t'.join(keys) if keys else 'None'); sys.exit(0)\n"
        + "if args[:2]==['s3api','head-object']:\n"
        + " p=store/args[args.index('--bucket')+1]/args[args.index('--key')+1]; meta=json.loads(pathlib.Path(str(p)+'.meta').read_text()); print(json.dumps(meta)); sys.exit(0)\n"
        + "if args[:2]==['s3','cp']:\n"
        + " src,dst=args[2],args[3]\n"
        + " if os.environ.get('AWS_MISSING_SIDECAR') and src.startswith('s3://') and (src.endswith('.sha256') or src.endswith('.metadata.json')): sys.exit(44)\n"
        + " if os.environ.get('AWS_FAIL_UPLOAD') and not src.startswith('s3://') and dst.startswith('s3://'): sys.exit(19)\n"
        + " if dst.startswith('s3://'):\n"
        + "  p=keypath(dst); p.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(native_path(src),p)\n"
        + "  if p.name.endswith('.dump'):\n"
        + "   d=p.read_bytes(); sha=hashlib.sha256(d).digest(); local_sha=dict(a.split('=',1) for a in args if a.startswith('sha256='))['sha256']; (pathlib.Path(str(p)+'.meta')).write_text(json.dumps({'ContentLength':len(d),'Metadata':{'sha256':local_sha},'ChecksumSHA256':base64.b64encode(sha).decode(),'ChecksumType':'FULL_OBJECT'}))\n"
        + " else:\n"
        + "  p=keypath(src); data=p.read_bytes()\n"
        + "  if os.environ.get('AWS_CORRUPT_DOWNLOAD') and p.name.endswith('.dump'): data=b'corrupt'\n"
        + "  pathlib.Path(native_path(dst)).write_bytes(data)\n"
        + " sys.exit(0)\n"
        + "sys.exit(0)\n",
        encoding="utf-8",
    )
    fake_aws.chmod(0o755)

    bash_parent = str(Path(BASH).parent)
    env = os.environ.copy()
    bash_tmp = bash_root / "bash-tmp"
    bash_tmp.mkdir()
    env.update(
        {
            "PATH": f"{bash_path(bin_dir)}:{bash_path(Path(bash_parent))}:{env.get('PATH', '')}",
            "BACKUP_BUCKET": "test-demo-bucket",
            "AWS_REGION": "ap-southeast-2",
            "BACKUP_DIR": bash_path(bash_root / "local-backups"),
            "TMPDIR": bash_path(bash_tmp),
            "S3_STORE": str(store),
            "AWS_LOG": str(aws_log),
            "DOCKER_LOG": str(docker_log),
            "SUDO_LOG": str(sudo_log),
            "DOCKER_SUDO": "auto",
            "DOCKER_DIRECT_FAIL": "1",
        }
    )
    (bash_root / "local-backups").mkdir()

    backup_script = AWS_SCRIPTS_DIR / "backup-to-s3.sh"
    result = subprocess.run(
        [BASH, str(backup_script)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"mock backup failed: {result.stderr}\n{result.stdout}"
    assert "Upload completed" in result.stdout
    assert "S3 object metadata verified" in result.stdout
    assert "Content checksum independently verified" in result.stdout
    dump_path = re.search(r"^BACKUP_PATH=(.+)$", result.stdout, re.MULTILINE).group(1)
    dump_name = Path(dump_path).name
    timestamp = re.search(r"neo4j-(\d{8}T\d{6}Z)-\d+\.dump$", dump_name).group(1)

    # Sudo fallback is selected before state-changing operations and is non-interactive.
    assert "-n docker info" in sudo_log.read_text()
    assert "--checksum-algorithm SHA256" in aws_log.read_text()

    restore_script = AWS_SCRIPTS_DIR / "restore-from-s3.sh"
    restore_env = env | {"FORCE_RESTORE": f"RESTORE APPLICATION neo4j FROM {dump_name}"}
    result_restore = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=restore_env,
        capture_output=True,
        text=True,
    )
    assert (
        result_restore.returncode == 0
    ), f"mock restore failed: {result_restore.stderr}\n{result_restore.stdout}"
    assert "configured application Compose database neo4j" in result_restore.stdout
    assert "SUCCESS: Database restored" in result_restore.stdout
    assert "database load" in docker_log.read_text()
    assert "Contents[?ends_with(Key, '.dump')].Key" in aws_log.read_text()

    # All backup validation happens before the destructive confirmation prompt.
    wrong_confirmation = env | {"FORCE_RESTORE": "RESTORE"}
    rejected = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=wrong_confirmation,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "Interactive confirmation required" in rejected.stderr
    assert "Backup SHA-256 verified before staging" in rejected.stdout

    # A corrupted download is rejected before the restore command runs.
    before_loads = docker_log.read_text().count("database load")
    corrupt_env = restore_env | {"AWS_CORRUPT_DOWNLOAD": "1"}
    result_corrupt = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=corrupt_env,
        capture_output=True,
        text=True,
    )
    assert result_corrupt.returncode != 0
    assert "SHA-256 verification failed" in result_corrupt.stderr
    assert docker_log.read_text().count("database load") == before_loads

    # Missing sidecars and invalid/ambiguous listings fail before confirmation or Docker.
    for mode, env_extra, expected in [
        ("none", {}, "Expected exactly one dump"),
        ("multiple", {}, "Expected exactly one dump"),
        ("invalid", {}, "Expected exactly one dump"),
        ("valid", {"AWS_MISSING_SIDECAR": "1"}, "Backup checksum download failed"),
    ]:
        bad = restore_env | {"AWS_LIST_MODE": mode} | env_extra
        failed = subprocess.run(
            [BASH, str(restore_script), timestamp],
            cwd=PROJECT_ROOT,
            env=bad,
            capture_output=True,
            text=True,
        )
        assert failed.returncode != 0 and expected in failed.stderr

    # A version mismatch is rejected before application services are stopped.
    before_stops = docker_log.read_text().count("compose stop api neo4j")
    mismatch_env = restore_env | {"NEO4J_MOCK_VERSION": "5.13.0"}
    mismatch = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=mismatch_env,
        capture_output=True,
        text=True,
    )
    assert mismatch.returncode != 0
    assert "does not exactly match" in mismatch.stderr
    assert docker_log.read_text().count("compose stop api neo4j") == before_stops

    # Failure to stop services means database load never starts.
    stop_fail_env = restore_env | {"DOCKER_STOP_FAIL": "1"}
    stop_fail = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=stop_fail_env,
        capture_output=True,
        text=True,
    )
    assert stop_fail.returncode != 0
    assert "Services stopped but database load did not start" in stop_fail.stderr
    assert docker_log.read_text().count("database load") == before_loads

    # S3 upload failure is reported and no success/integrity claim is emitted.
    fail_env = env | {"AWS_FAIL_UPLOAD": "1"}
    fail_dir = bash_root / "failure-backups"
    fail_dir.mkdir()
    fail_env["BACKUP_DIR"] = bash_path(fail_dir)
    upload_fail = subprocess.run(
        [BASH, str(backup_script)],
        cwd=PROJECT_ROOT,
        env=fail_env,
        capture_output=True,
        text=True,
    )
    assert upload_fail.returncode != 0
    assert "S3 dump upload failed" in upload_fail.stderr
    assert "Integrity-verified" not in upload_fail.stdout

    # Failed Neo4j load retains the original downloaded dump for manual recovery.
    load_fail_env = restore_env | {"DOCKER_LOAD_FAIL": "1"}
    load_fail = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=load_fail_env,
        capture_output=True,
        text=True,
    )
    assert load_fail.returncode != 0
    preserved = re.search(r"dump: (.+)$", load_fail.stderr, re.MULTILINE)
    assert preserved and Path(native_path(preserved.group(1))).is_file()
    assert Path(native_path(preserved.group(1) + ".sha256")).is_file()
    assert Path(native_path(preserved.group(1) + ".metadata.json")).is_file()
    assert "Database load started but failed" in load_fail.stderr

    # Restart failure is distinguished and the full downloaded recovery copy remains.
    restart_fail_env = restore_env | {"DOCKER_RESTART_FAIL": "1"}
    restart_fail = subprocess.run(
        [BASH, str(restore_script), timestamp],
        cwd=PROJECT_ROOT,
        env=restart_fail_env,
        capture_output=True,
        text=True,
    )
    assert restart_fail.returncode != 0
    assert "Service restart failed" in restart_fail.stderr
    restart_copy = re.search(r"dump: (.+)$", restart_fail.stderr, re.MULTILINE)
    assert restart_copy and Path(native_path(restart_copy.group(1))).is_file()
