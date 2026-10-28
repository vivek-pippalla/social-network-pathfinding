#!/usr/bin/env bash
# ==============================================================================
# ec2_setup.sh — Automated Host Provisioning for Social Network Pathfinding
#
# Target OS: Ubuntu 22.04 / 24.04 LTS on AWS EC2 (t3.medium recommended)
#
# Tasks performed:
#   1. System updates & essential tooling installation
#   2. 2GB Swap space allocation (critical buffer for Neo4j memory spikes)
#   3. Docker Engine & Docker Compose plugin installation
#   4. AWS CLI v2 installation
#   5. User permissions & application directory structure creation
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo " Starting EC2 Host Provisioning..."
echo "=========================================================="

# 1. Update system packages
echo "[1/6] Updating APT repositories..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    jq \
    unzip \
    git

# 2. Configure 2GB Swap File (Buffer against JVM OOM)
echo "[2/6] Configuring 2GB Swap space..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "Swap created successfully."
else
    echo "Swapfile already exists. Skipping."
fi

# 3. Install Docker Engine
echo "[3/6] Installing Docker Engine..."
if ! command -v docker &>/dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Enable and start docker
    sudo systemctl enable docker
    sudo systemctl start docker

    # Add current user to docker group
    sudo usermod -aG docker "$USER"
    echo "Docker installed successfully."
else
    echo "Docker already installed."
fi

# 4. Install AWS CLI v2
echo "[4/6] Installing AWS CLI v2..."
if ! command -v aws &>/dev/null; then
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
    echo "AWS CLI installed: $(aws --version)"
else
    echo "AWS CLI already installed: $(aws --version)"
fi

# 5. Create Application Workspace Directory
echo "[5/6] Setting up application workspace..."
APP_DIR="/opt/social-network-pathfinding"
sudo mkdir -p "$APP_DIR" "$APP_DIR/caddy" "$APP_DIR/scripts"
sudo chown -R "$USER:$USER" "$APP_DIR"
chmod 755 "$APP_DIR"

# 6. Verify Docker Installation
echo "[6/6] Verifying Docker daemon..."
docker --version
docker compose version

echo "=========================================================="
echo " EC2 Provisioning Complete!"
echo " Log out and log back in (or run 'newgrp docker') for docker group permissions to take effect."
echo " Application directory: $APP_DIR"
echo "=========================================================="
