# AWS Demonstration Deployment Runbook

This directory contains the deployment kit, IAM policies, Compose overlays, and operational scripts for deploying the Social Network Pathfinding project to a single Amazon EC2 instance for portfolio demonstration.

---

## 1. Architecture Overview

- **Host:** Single Amazon EC2 instance running **Amazon Linux 2023** (x86_64, 4–8 GiB RAM recommended).
- **Network Ingress:** Default VPC; Security Group strictly restricts TCP port 22 (SSH) and TCP port 80 (HTTP) to your current public workstation IP (`<MY_PUBLIC_IP>/32`).
- **Internal Micro-Segmentation:** Caddy handles edge HTTP traffic on port 80. The application API (5000), Neo4j (7474, 7687), and Redis (6379) are unexposed to the host network and internet.
- **Durable State:** Neo4j graph data lives on a 20 GiB gp3 root EBS volume (*Delete on termination: true*). Periodic backup dumps are archived to Amazon S3.
- **Logging & Monitoring:** Docker `awslogs` log driver streams container output to CloudWatch log group `/pathfinding-demo` with 7-day retention in non-blocking mode.
- **Identity & Security:** IAM instance role (`pathfinding-demo-ec2-role`) with IMDSv2 required (hop limit 1). No AWS access keys exist on disk.

---

## 2. Preparation Checklist (Before Launching EC2)

1. **Billing Guardrail:** Create an AWS Budget with a **$10 monthly ceiling** and email notifications at 50% and 80% actual spend.
2. **S3 Bucket:** Create private S3 bucket `<BUCKET_NAME>` with Block Public Access enabled and default encryption on. Apply lifecycle rule from `iam/s3-lifecycle.json`.
3. **CloudWatch Log Group:** Create `/pathfinding-demo` with **7 days retention**.
4. **IAM Role:** Create IAM role `pathfinding-demo-ec2-role` with trust policy `iam/ec2-trust-policy.json` and permissions policy `iam/ec2-instance-policy.json`. Attach to an instance profile of the same name.
5. **Key Pair:** Create an EC2 key pair (e.g. `pathfinding-demo-key.pem`), saved locally with `chmod 400`.
6. **Public IP:** Lookup your public IP: `curl -s https://checkip.amazonaws.com` and note `<MY_PUBLIC_IP>/32`.
7. **Security Group:** Create `pathfinding-demo-sg` with inbound rules:
   - TCP 22 from `<MY_PUBLIC_IP>/32`
   - TCP 80 from `<MY_PUBLIC_IP>/32`

---

## 3. Deployment Procedure (Step-by-Step)

### Step 1: Launch EC2 Instance
- AMI: **Amazon Linux 2023** (64-bit x86)
- Instance Type: `c7i-flex.large` (4 GB), `m7i-flex.large` (8 GB), or `t3.small` (2 GB + swap)
- Security Group: `pathfinding-demo-sg`
- Root Volume: 20 GiB gp3 (*Delete on termination: true*)
- Advanced: IAM Instance Profile `pathfinding-demo-ec2-role`; IMDSv2 Required; Hop limit: 1.

### Step 2: Connect via SSH
```bash
ssh -i /path/to/<KEY_PAIR_NAME>.pem ec2-user@<PUBLIC_IP>
```

### Step 3: Run Host Bootstrap
```bash
# Clone the repository onto the instance
git clone https://github.com/<GITHUB_OWNER>/social-network-pathfinding.git
cd social-network-pathfinding

# Run bootstrap script (installs Docker, Compose v2, Git, jq, and swap)
./deploy/aws/scripts/bootstrap-ec2.sh

# Re-login to apply docker group
exit
ssh -i /path/to/<KEY_PAIR_NAME>.pem ec2-user@<PUBLIC_IP>
cd social-network-pathfinding
```

### Step 4: Configure Environment
```bash
cp deploy/aws/env.aws.example .env
chmod 600 .env

# Generate independent secrets on the instance (never committed)
SECRET_KEY=$(openssl rand -hex 32)
NEO4J_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)
REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)

# Edit .env and supply the generated secrets, AWS_REGION, and BACKUP_BUCKET
nano .env
```

### Step 5: Start Stack
```bash
# Validate Compose configuration without printing resolved secrets
docker compose config --no-interpolate | grep -nE 'ports:|logging:|driver:'

# Deploy using automated deployment & healthcheck script
./deploy/local/deploy.sh
```

### Step 6: Ingest Dataset & Seed Demo Account
```bash
docker compose run --rm api python -m app.cli ingest
docker compose run --rm api python -m app.cli demo-user
```

### Step 7: Run Verification Suite
```bash
# Run verification locally on the instance
./deploy/aws/scripts/verify.sh

# Run verification remotely from your laptop
BASE_URL="http://<PUBLIC_IP>" ./deploy/aws/scripts/verify.sh
```

---

## 4. Operational Scripts

- **`scripts/bootstrap-ec2.sh`**: Installs Docker Engine, Docker Compose v2, Git, jq, and sets up swap.
- **`scripts/backup-to-s3.sh`**: Dumps Neo4j database, computes SHA-256 digest, and archives to S3.
- **`scripts/restore-from-s3.sh <PREFIX>`**: Downloads backup from S3, validates SHA-256 integrity, and restores database.
- **`scripts/verify.sh`**: Comprehensive health, auth, pathfinding, and cache verification suite.

---

## 5. Decommissioning & Cleanup

Immediately after capturing evidence, follow [cleanup-checklist.md](cleanup-checklist.md) to terminate the EC2 instance and delete cloud resources.
