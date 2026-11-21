# AWS Demonstration Deployment Runbook

This directory contains the deployment kit, IAM policies, Compose overlays, and operational scripts for deploying the Social Network Pathfinding project to a single Amazon EC2 instance for portfolio demonstration.

---

## 1. Architecture Overview

- **Host:** Single EC2 instance running **Ubuntu 24.04** (the configured environment uses `m7i-flex.large`, 8 GiB RAM).
- **Network Ingress:** Default VPC; Security Group strictly restricts TCP port 22 (SSH) and TCP port 80 (HTTP) to your current public workstation IP (`<MY_PUBLIC_IP>/32`).
- **Internal Micro-Segmentation:** Caddy handles edge HTTP traffic on port 80. The application API (5000), Neo4j (7474, 7687), and Redis (6379) are unexposed to the host network and internet.
- **Durable State:** Neo4j graph data lives on a 20 GiB gp3 root EBS volume (*Delete on termination: true*). Periodic backup dumps are archived to Amazon S3.
- **Logging & Monitoring:** Docker `awslogs` log driver streams container output to CloudWatch log group `/pathfinding-demo` with 7-day retention in non-blocking mode.
- **Identity & Security:** IAM instance role (`graph-project-ec2-role`) with IMDSv2 required (hop limit 1). No AWS access keys exist on disk.

---

## 2. Preparation Checklist (Before Launching EC2)

1. **Billing Guardrail:** Create an AWS Budget with a **$10 monthly ceiling** and email notifications at 50% and 80% actual spend.
2. **S3 Bucket:** Use `graph-project-backups-unique-number` in `ap-southeast-2`; keep Block Public Access enabled and default encryption on. Review lifecycle policy carefully before applying it to preserve existing backups.
3. **CloudWatch Log Group:** Create `/pathfinding-demo` with **7 days retention**.
4. **IAM Role:** Use the existing `graph-project-ec2-role`. The example policy in `iam/ec2-instance-policy.json` is a template with account and bucket placeholders; it is not an instruction to replace the existing role policy.
5. **Key Pair:** Create an EC2 key pair (e.g. `pathfinding-demo-key.pem`), saved locally with `chmod 400`.
6. **Public IP:** Lookup your public IP: `curl -s https://checkip.amazonaws.com` and note `<MY_PUBLIC_IP>/32`.
7. **Security Group:** Create `pathfinding-demo-sg` with inbound rules:
   - TCP 22 from `<MY_PUBLIC_IP>/32`
   - TCP 80 from `<MY_PUBLIC_IP>/32`

---

## 3. Deployment Procedure (Step-by-Step)

### Step 1: EC2 Host
- Supported OS: **Ubuntu 24.04** (64-bit x86)
- Instance Type: `m7i-flex.large` (8 GiB)
- Security Group: `pathfinding-demo-sg`
- Root Volume: 20 GiB gp3 (*Delete on termination: true*)
- Advanced: existing IAM Instance Profile `graph-project-ec2-role`; IMDSv2 Required; Hop limit: 1.

### Step 2: Connect via SSH
```bash
ssh -i /path/to/<KEY_PAIR_NAME>.pem ubuntu@<PUBLIC_IP>
```

### Step 3: Run Host Bootstrap
```bash
# Clone the repository onto the instance
git clone https://github.com/<GITHUB_OWNER>/social-network-pathfinding.git
cd social-network-pathfinding

# Run bootstrap script (installs Docker, Compose v2, Git, jq, and swap)
bash deploy/aws/scripts/bootstrap-ec2.sh

# Re-login to apply docker group
exit
ssh -i /path/to/<KEY_PAIR_NAME>.pem ubuntu@<PUBLIC_IP>
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

# Edit .env and supply the generated secrets; keep AWS_REGION and BACKUP_BUCKET aligned with the existing environment.
nano .env
```

### Step 5: Start Stack
```bash
# Validate Compose configuration without printing resolved secrets
docker compose config --no-interpolate | grep -nE 'ports:|logging:|driver:'

# Deploy using automated deployment & healthcheck script
bash deploy/local/deploy.sh
```

### Step 6: Ingest Dataset & Seed Demo Account
```bash
docker compose run --rm api python -m app.cli ingest
docker compose run --rm api python -m app.cli demo-user
```

### Step 7: Run Verification Suite
```bash
# Run verification locally on the instance
bash deploy/aws/scripts/verify.sh

# Run verification remotely from your laptop
BASE_URL="http://<PUBLIC_IP>" bash deploy/aws/scripts/verify.sh
```

---

## 4. Operational Scripts

- **`scripts/bootstrap-ec2.sh`**: Installs Docker Engine, Compose v2, Git, jq, AWS CLI, and configures swap only on hosts with at most 2 GiB RAM. Supports Ubuntu 24.04.
- **`deploy/aws/scripts/backup-to-s3.sh`**: Uploads one identified dump and verifies downloaded S3 object bytes against SHA-256.
- **`deploy/aws/scripts/restore-from-s3.sh <UTC_TIMESTAMP>`**: Downloads exactly one dump for the timestamp, verifies it, and requires explicit confirmation before replacing current graph data.
- **`deploy/aws/scripts/verify.sh`**: Set `GRAPH_START_ID` and `GRAPH_END_ID` to known connected dataset nodes to check pathfinding and cache; otherwise these checks are reported as skipped. Rate-limit probing is opt-in with `--test-rate-limit`.

Backup and restore use `DOCKER_SUDO=auto` by default. Set it to `never` to require direct Docker socket access or `always` to use non-interactive `sudo -n docker`; the scripts do not change socket permissions. Restore is supported only for backups made with the current dump, SHA-256, and Neo4j-version metadata sidecars. Older backups without version metadata are intentionally rejected because compatibility cannot be validated safely. The restore script targets the Compose application database `neo4j`; it does not provide an isolated/test target. Use a separately configured Compose project and data volume for restore drills.

### IAM notes

The supplied instance policy grants `CreateLogStream` and `PutLogEvents` for the pre-created `/pathfinding-demo` log group. The log group must already exist. These permissions cover the Docker `awslogs` driver; the example does not install or run the CloudWatch Agent. If host metrics from `iam/cloudwatch-agent-config.json` are later enabled, review and attach a separate least-privilege CloudWatch Agent policy for `cloudwatch:PutMetricData` and any EC2 metadata discovery actions required by that agent configuration. Keep those permissions separate from container logging. The EC2 role does not grant metric-reading actions: the operator or monitoring identity that queries metrics needs `cloudwatch:GetMetricStatistics` (and, if it discovers metric names dynamically, `cloudwatch:ListMetrics`). The historical missing `GetMetricStatistics` finding belongs to that reader identity and does not justify broadening the instance logging policy.

---

## 5. Decommissioning & Cleanup

Cleanup is a separate, explicitly approved operation. The existing EC2 instance, IAM role, CloudWatch log group, S3 bucket, and backup objects must be reviewed individually; do not apply the generic deletion checklist to shared or retained resources.
