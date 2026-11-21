#!/usr/bin/env bash
# Bootstrap supported Ubuntu 24.04 EC2 hosts with the repository's Docker tooling.
set -Eeuo pipefail

[[ -r /etc/os-release ]] || { echo 'ERROR: Cannot identify operating system.' >&2; exit 2; }
# shellcheck disable=SC1091
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then
    printf 'ERROR: Supported host is Ubuntu 24.04; detected %s %s.\n' "${ID:-unknown}" "${VERSION_ID:-unknown}" >&2
    exit 2
fi
if [[ $EUID -eq 0 ]]; then SUDO=();
elif command -v sudo >/dev/null 2>&1; then SUDO=(sudo);
else echo 'ERROR: Run as root or install/configure sudo.' >&2; exit 2; fi

echo 'Installing Docker Engine, Compose plugin, Git, jq, AWS CLI, and curl for Ubuntu 24.04.'
"${SUDO[@]}" apt-get update
"${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose-v2 git jq awscli curl ca-certificates
"${SUDO[@]}" systemctl enable --now docker

LOGIN_USER=${SUDO_USER:-${USER:-}}
if [[ -n $LOGIN_USER && $LOGIN_USER != root ]]; then
    "${SUDO[@]}" usermod -aG docker "$LOGIN_USER"
fi

TOTAL_MEM_MB=$(awk '/^MemTotal:/ {print int($2 / 1024)}' /proc/meminfo)
if [[ ${TOTAL_MEM_MB:-0} -le 2048 && ! -e /swapfile ]]; then
    echo "RAM is ${TOTAL_MEM_MB} MiB; creating a 2 GiB swapfile."
    "${SUDO[@]}" fallocate -l 2G /swapfile
    "${SUDO[@]}" chmod 600 /swapfile
    "${SUDO[@]}" mkswap /swapfile
    "${SUDO[@]}" swapon /swapfile
    if ! grep -qE '^/swapfile[[:space:]]' /etc/fstab; then
        printf '/swapfile none swap sw 0 0\n' | "${SUDO[@]}" tee -a /etc/fstab >/dev/null
    fi
fi

docker compose version
git --version
jq --version
aws --version
echo 'Bootstrap complete. Log out and back in to apply Docker group membership.'
