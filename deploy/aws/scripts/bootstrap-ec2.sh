#!/usr/bin/env bash
# ==============================================================================
# deploy/aws/scripts/bootstrap-ec2.sh — Host Bootstrap for Amazon Linux 2023
# Installs Docker, Compose v2 plugin, Git, jq, and configures swap if needed.
# ==============================================================================
set -euo pipefail

echo "=== Bootstrapping Amazon Linux 2023 Host ==="

# 1. Update system packages
echo "Updating system packages..."
sudo dnf update -y

# 2. Install essential packages (AWS CLI v2 is preinstalled on AL2023)
echo "Installing Docker, Git, and jq..."
sudo dnf install -y docker git jq

# 3. Enable and start Docker service
echo "Starting Docker service..."
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

# 4. Install Docker Compose v2 plugin
COMPOSE_VERSION="${COMPOSE_VERSION:-v2.29.7}"
echo "Installing Docker Compose ${COMPOSE_VERSION}..."
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 5. Configure swap if instance RAM <= 2GB
TOTAL_MEM_MB=$(free -m | awk '/^Mem:/{print $2}')
if [ "${TOTAL_MEM_MB:-0}" -le 2048 ] && [ ! -f /swapfile ]; then
    echo "RAM is <= 2GB (${TOTAL_MEM_MB}MB). Creating 2GB swapfile..."
    sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap configured successfully."
fi

# 6. Verify tooling
echo "Verifying installed tooling:"
docker compose version
aws --version
git --version

echo "=== Bootstrap Complete ==="
echo "Note: Log out and back in to apply Docker group membership: exit"
