# AWS Production Deployment & Architecture Guide

A lean, production-grade guide for deploying the **Social Network Pathfinding Engine** to Amazon Web Services using **EC2, S3, IAM, CloudWatch, and ECR**, with automated CI/CD via **GitHub Actions and AWS OIDC federation**.

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Target AWS Services & Justification](#target-aws-services--justification)
3. [Pre-Launch Cost Safeguard: AWS Budget Alert](#pre-launch-cost-safeguard-aws-budget-alert)
4. [Security Architecture & Trade-Offs](#security-architecture--trade-offs)
   - [Host Secrets (.env.prod) vs. Secrets Manager](#host-secrets-envprod-vs-secrets-manager)
   - [Ingress Architecture: Caddy Reverse Proxy & Automatic HTTPS](#ingress-architecture-caddy-reverse-proxy--automatic-https-0-extra-cost)
   - [Hostname Requirements & Verification (<EC2_PUBLIC_IP>.sslip.io)](#hostname-requirements--verification-ec2_public_ipsslipio)
   - [Safe TLS Certificate & State Persistence across Container Restarts](#safe-tls-certificate--state-persistence-across-container-restarts)
   - [Network Isolation: Strict Internal-Only Database & Application Ports](#network-isolation-strict-internal-only-database--application-ports)
   - [SSH Host-Key Verification & Independent Fingerprint Auditing](#ssh-host-key-verification--independent-fingerprint-auditing)
5. [Resource Sizing & Memory Planning](#resource-sizing--memory-planning)
6. [Windows / Git Bash Environment Compatibility Notes](#windows--git-bash-environment-compatibility-notes)
7. [Step-by-Step AWS Setup Commands (Git Bash & PowerShell)](#step-by-step-aws-setup-commands-git-bash--powershell)
   - [Step 1: Amazon S3 (Dataset Storage)](#step-1-amazon-s3-dataset-storage)
   - [Step 2: Amazon ECR (Container Registry)](#step-2-amazon-ecr-container-registry)
   - [Step 3: Amazon CloudWatch (Centralized Logs)](#step-3-amazon-cloudwatch-centralized-logs)
   - [Step 4: AWS IAM (Least-Privilege Roles & Policies)](#step-4-aws-iam-least-privilege-roles--policies)
   - [Step 5: Amazon EC2 (Host Instance & Security Groups)](#step-5-amazon-ec2-host-instance--security-groups)
8. [GitHub Actions CI/CD with OIDC Setup](#github-actions-cicd-with-oidc-setup)
9. [Host Provisioning, Healthchecks & Automated Rollback](#host-provisioning-healthchecks--automated-rollback)
10. [Ongoing Charges After EC2 is Stopped](#ongoing-charges-after-ec2-is-stopped)
11. [Troubleshooting & Runbook](#troubleshooting--runbook)
12. [Teardown & Cleanup Procedures](#teardown--cleanup-procedures)

---

## Architectural Overview

```
                                      AWS Cloud (ap-south-1)
 ┌─────────────────────────────────────────────────────────────────────────────────────────┐
 │                                                                                         │
 │   ┌──────────────────────┐              ┌───────────────────────────────────────────┐   │
 │   │      Amazon S3       │              │           Amazon CloudWatch Logs          │   │
 │   │ (Private Dataset)    │              │   (/social-network-pathfinding/app)       │   │
 │   └──────────┬───────────┘              └─────────────────────▲─────────────────────┘   │
 │              │ (IAM Auth / seed_data.py)                      │ (Structured JSON logs)  │
 │              ▼                                                │                         │
 │   ┌───────────────────────────────────────────────────────────┴─────────────────────┐   │
 │   │ Amazon EC2 (t3.medium: 2 vCPU, 4GB RAM + 2GB Swap)                              │   │
 │   │                                                                                 │   │
 │   │  Security Group: Inbound 22 (SSH Admin: MY_IP/32), Inbound 80 (HTTP), 443 (HTTPS)│  │
 │   │  IAM Instance Profile: EC2InstanceRole                                          │   │
 │   │  Environment: /opt/social-network-pathfinding/.env.prod (chmod 600, not in Git) │   │
 │   │                                                                                 │   │
 │   │   ┌─────────────────────────────────────────────────────────────────────────┐   │   │
 │   │   │ Docker Network: internal-network (Bridge)                               │   │   │
 │   │   │                                                                         │   │   │
 │   │   │   ┌───────────────────────────┐                                         │   │   │
 │   │   │   │ Caddy 2.8 Reverse Proxy   │ (Host: 80, 443 -> Auto Let's Encrypt)   │   │   │
 │   │   │   │ (social-network-caddy)    │ (Auto HTTP->HTTPS 308 redirect)         │   │   │
 │   │   │   └─────────────┬─────────────┘                                         │   │   │
 │   │   │                 │ (Internal HTTP proxy to api:5000)                     │   │   │
 │   │   │                 ▼                                                       │   │   │
 │   │   │   ┌───────────────────────────┐      ┌───────────────────────────────┐  │   │   │
 │   │   │   │ FastAPI App (Internal)    │─────▶│      Redis 7 Cache (LRU)      │  │   │   │
 │   │   │   │ (Port 5000 Unpublished)   │      │      (Internal port 6379)     │  │   │   │
 │   │   │   └─────────────┬─────────────┘      │      (Unpublished to Host)    │  │   │   │
 │   │   │                 │                    └───────────────────────────────┘  │   │   │
 │   │   │                 ▼                                                       │   │   │
 │   │   │   ┌───────────────────────────┐                                         │   │   │
 │   │   │   │ Neo4j 5.12 Graph DB       │                                         │   │   │
 │   │   │   │ (Internal 7687, 7474)     │                                         │   │   │
 │   │   │   │ (Unpublished to Host)     │                                         │   │   │
 │   │   │   └───────────────────────────┘                                         │   │   │
 │   │   └─────────────────────────────────────────────────────────────────────────┘   │   │
 │   └─────────────────────────────────────────▲───────────────────────────────────────┘   │
 │                                             │                                           │
 │   ┌──────────────────────┐                  │ (ecr pull via Instance Role)              │
 │   │      Amazon ECR      │──────────────────┘                                           │
 │   │ (social-network-api) │                                                              │
 │   └──────────▲───────────┘                                                              │
 │              │ (docker push via OIDC)                                                   │
 └──────────────┼──────────────────────────────────────────────────────────────────────────┘
                │
 ┌──────────────┴──────────────────────────────────────────────────────────────────────────┐
 │ GitHub Actions (CI/CD)                                                                  │
 │ - Trigger: Push to main                                                                 │
 │ - Authentication: AWS STS AssumeRoleWithWebIdentity (Keyless OIDC token)                 │
 │ - Verification: Strictly requires pinned EC2_SSH_KNOWN_HOSTS (no dynamic TOFU)         │
 │ - Jobs: Run 54 Pytest Unit Tests -> Build Docker Image -> Push to ECR -> SSH Deploy    │
 └─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Target AWS Services & Justification

| AWS Service | Production Purpose | Why Selected? |
|---|---|---|
| **EC2** | Hosts the containerized stack (FastAPI, Neo4j, Redis) on a unified virtual machine. | Eliminates expensive managed orchestrators (ECS/EKS) and Application Load Balancers ($18+/mo base fee). |
| **S3** | Stores gzipped Facebook social graph dataset (`datasets/facebook_combined.txt.gz`). | High-durability, cost-effective object storage (pennies/month), IAM-secured without public URLs. |
| **IAM** | Enforces least-privilege policies for EC2 and GitHub Actions; GitHub OIDC federation. | Eliminates high-risk, permanent IAM user access keys. |
| **CloudWatch** | Centralizes single-line structured JSON logs with stream auto-naming and retention. | Built-in log shipping via `watchtower` without maintaining ElasticSearch / OpenSearch clusters. |
| **ECR** | Private container registry for versioned production images. | Secure container storage integrated natively with IAM instance roles. |

---

## Pre-Launch Cost Safeguard: AWS Budget Alert

> [!IMPORTANT]
> Before launching any EC2 instance or cloud resource, configure an AWS Budget Alert to notify you via email if your estimated monthly bill exceeds **$5.00 USD**.

### Option A: AWS Console (Recommended)
1. Go to **AWS Billing & Cost Management Console** $\rightarrow$ **Budgets**.
2. Click **Create budget** $\rightarrow$ Choose **Cost budget (Recommended)**.
3. Set **Budget amount**: `$5.00` (Monthly, Fixed).
4. Under **Alert thresholds**, set:
   - **80% of budgeted amount ($4.00)**: triggers an email notification when forecasted or actual spend hits $4.00.
   - **100% of budgeted amount ($5.00)**: triggers an immediate critical alert.
5. Enter your email address and click **Create budget**.

### Option B: AWS CLI
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text | tr -d '\r')

aws budgets create-budget \
    --account-id "$ACCOUNT_ID" \
    --budget '{
        "BudgetName": "SocialNetwork-Monthly-Guardrail",
        "BudgetLimit": {"Amount": "5.0", "Unit": "USD"},
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST"
    }' \
    --notifications-with-subscribers '[{
        "Notification": {
            "NotificationType": "ACTUAL",
            "ComparisonOperator": "GREATER_THAN",
            "Threshold": 80.0,
            "ThresholdType": "PERCENTAGE"
        },
        "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "your-email@example.com"}]
    }]'
```

---

## Security Architecture & Trade-Offs

### Host Secrets (.env.prod) vs. Secrets Manager
For this single-host EC2 architecture, production credentials (`NEO4J_PASSWORD` and `SECRET_KEY`) are managed via a server-side `.env.prod` file:

1. **Zero Startup Network Latency & Failure Modes:** Calling AWS Secrets Manager on container boot introduces an external network dependency. Transient network timeouts or API throttling can cause container boot loops. Host environment variables guarantee deterministic startup.
2. **Elimination of Recurring Costs:** Secrets Manager charges $0.40/month per secret plus $0.05 per 10,000 API calls. For 2 static values on a single host, this adds unnecessary cost.
3. **Reduced IAM Attack Surface:** The EC2 instance role requires no `secretsmanager:GetSecretValue` permissions, strictly limiting host privileges to S3 reading, CloudWatch log writing, and ECR pulling.

### Ingress Architecture: Caddy Reverse Proxy & Automatic HTTPS ($0 Extra Cost)

To provide production-grade TLS encryption and automatic certificate management without incurring recurring AWS Application Load Balancer fees ($18–$22/month), the stack deploys **Caddy 2.8** as a reverse proxy container alongside FastAPI:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Public Internet                                                                                 │
│                                                                                                 │
│  HTTP Request (Port 80)  ──▶ [Caddy Reverse Proxy] ──▶ HTTP 308 Redirect (Force HTTPS)          │
│                                      │                                                          │
│  HTTPS Request (Port 443) ─▶ [Caddy Reverse Proxy]                                              │
│                                      │                                                          │
│                           Terminates TLS (Let's Encrypt / ZeroSSL)                              │
│                           Injects HSTS, nosniff, frame protection headers                       │
│                                      │                                                          │
│                                      ▼ (Internal Bridge Network: internal-network)              │
│                               ┌──────────────┐                                                  │
│                               │ FastAPI App  │ (Listens on port 5000, UNMAPPED to Host)         │
│                               └──────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Key Capabilities of the Caddy Reverse Proxy:
1. **Automatic HTTPS:** Caddy manages the full certificate lifecycle (issuance, OCSP stapling, and automatic renewal 30 days before expiration) via ACME protocol with Let's Encrypt and ZeroSSL.
2. **HTTP to HTTPS Redirection:** Port 80 automatically issues an `HTTP 308 Permanent Redirect` to HTTPS on port 443.
3. **Internal Reverse Proxying:** Port 5000 is never exposed on the host. Caddy proxies decrypted traffic internally over Docker's bridge network to `http://api:5000`.
4. **Hardened Security Headers:** Caddyfile enforces HTTP Strict Transport Security (`HSTS`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and strips the server identification header (`-Server`).

### Hostname Requirements & Verification (<EC2_PUBLIC_IP>.sslip.io)

Caddy automatically requests and validates TLS certificates when supplied with a valid Fully Qualified Domain Name (FQDN):

1. **Zero-Cost Dynamic Wildcard DNS (`<EC2_PUBLIC_IP>.sslip.io`):**
   - If you do not own a custom domain, use `sslip.io`. For example, if your EC2 public IP is `13.233.45.67`, set `DOMAIN_NAME=13.233.45.67.sslip.io`.
   - `sslip.io` maps `<ip>.sslip.io` directly to `<ip>` via public DNS without registration or fees.
   - **Public Suffix List (PSL) Compatibility:** `sslip.io` is listed on the Mozilla Public Suffix List. Consequently, Let's Encrypt rate limits (50 certificates per registered domain per week) apply per IP subdomain, preventing rate limit throttling from other users.
2. **Custom Domain Alternative:**
   - If you own a domain (e.g. `api.yourdomain.com`), configure an `A` record pointing to your EC2 public IP address.
3. **Port 80 Accessibility Requirement:**
   - Let's Encrypt uses the ACME **HTTP-01 challenge**. The Let's Encrypt CA server sends an HTTP GET request to `http://<DOMAIN_NAME>/.well-known/acme-challenge/<token>` on **port 80**.
   - If inbound port 80 is closed in the EC2 Security Group, domain ownership validation will fail, and Caddy cannot issue the TLS certificate.
4. **Local Validation vs. Live Deployment Distinction:**
   - **Local Validation (Current Phase):** Validates Caddyfile syntax, Docker Compose wiring, container health checks, network topology, and rollback mechanics without contacting external ACME servers.
   - **Live Deployment (AWS Phase):** Only after EC2 is launched with a real public IP, port 80 is reachable, and the domain resolves can Let's Encrypt complete the HTTP-01 challenge and issue the certificate.

### Safe TLS Certificate & State Persistence across Container Restarts

ACME CAs enforce strict rate limits on duplicate certificate orders (e.g., Let's Encrypt limit of 5 duplicate certificates per week). To ensure certificates and keys survive container recreation, upgrades, and host reboots:

- **`caddy_data:/data`:** Docker named volume that permanently stores issued TLS certificates, private keys, and ACME account metadata on the EC2 host.
- **`caddy_config:/config`:** Docker named volume that persists Caddy's autosaved configuration and runtime state.
- **Graceful Lifecycle:** When the API is upgraded via `deploy_prod.sh`, the Caddy container preserves all existing certificates without re-triggering ACME issuance.

### Network Isolation: Strict Internal-Only Database & Application Ports

The production network topology strictly restricts public ingress:
- **Port 80 (HTTP):** Open to `0.0.0.0/0` (for ACME challenges and automatic HTTPS redirection).
- **Port 443 (HTTPS):** Open to `0.0.0.0/0` (for encrypted API traffic).
- **Port 22 (SSH):** Restricted strictly to operator IP (`MY_IP/32`).
- **Port 5000 (FastAPI):** **UNPUBLISHED** to host. Accessible solely via Caddy inside `internal-network`.
- **Ports 7474, 7687 (Neo4j):** **UNPUBLISHED** to host. Accessible solely via internal containers.
- **Port 6379 (Redis):** **UNPUBLISHED** to host. Accessible solely via internal containers.

### SSH Host-Key Verification & Independent Fingerprint Auditing

To protect the CI/CD pipeline from Man-in-the-Middle (MITM) attacks, `.github/workflows/ci.yml` strictly requires a pinned `EC2_SSH_KNOWN_HOSTS` secret.

#### How to Obtain and Independently Verify the EC2 Host Key:
When an Ubuntu EC2 instance boots for the first time, `cloud-init` generates unique SSH host keys and prints both the **SHA256 fingerprints** and the **raw public keys** to the system console. This provides a **trusted out-of-band channel** directly from the hypervisor.

1. **Step 1: Retrieve the Console Output via AWS CLI:**
   ```bash
   aws ec2 get-console-output --instance-id "$INSTANCE_ID" --output text > ec2_console.log
   ```
   Inspect the SSH keys and fingerprints output:
   ```bash
   grep -A 10 "BEGIN SSH HOST KEY" ec2_console.log
   ```
   Ubuntu `cloud-init` prints two blocks:
   ```text
   -----BEGIN SSH HOST KEY FINGERPRINTS-----
   256 SHA256:4t7XmK... root@ip-172-31-xx-yy (ED25519)
   256 SHA256:8b9YnZ... root@ip-172-31-xx-yy (ECDSA)
   3072 SHA256:9c0ZoA... root@ip-172-31-xx-yy (RSA)
   -----END SSH HOST KEY FINGERPRINTS-----

   -----BEGIN SSH HOST KEY KEYS-----
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... root@ip-172-31-xx-yy
   ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoY... root@ip-172-31-xx-yy
   ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAB... root@ip-172-31-xx-yy
   -----END SSH HOST KEY KEYS-----
   ```

2. **Step 2 (Method A - Recommended & Direct): Construct Known Hosts from Hypervisor Output:**
   Because the raw public key comes straight from the AWS hypervisor console, you can construct the `known_hosts` entry directly with zero network scanning:
   ```text
   <EC2_HOST> ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...
   ```
   *(Replace `<EC2_HOST>` with the exact IP or DNS hostname used in `secrets.EC2_HOST`, followed by the exact `ssh-ed25519` key string from `BEGIN SSH HOST KEY KEYS`).*

3. **Step 2 (Method B - Alternative): Scan Locally and Verify Fingerprint:**
   If you prefer using `ssh-keyscan`:
   ```bash
   # Use relative path ./scanned_host_key (works in Git Bash, PowerShell, and Linux)
   ssh-keyscan -H <EC2_HOST> > ./scanned_host_key

   # Verify the fingerprint matches the console log
   ssh-keygen -lf ./scanned_host_key
   ```
   Confirm that the calculated SHA256 hash matches the `(ED25519)` line in `-----BEGIN SSH HOST KEY FINGERPRINTS-----` from Step 1.

4. **Step 3: Store in GitHub Secrets:**
   Copy the verified host key entry (single line) and add it as **`EC2_SSH_KNOWN_HOSTS`** under GitHub **Settings > Secrets and variables > Actions**.

> [!IMPORTANT]
> **Matching Host Rule:** The hostname or IP passed to `ssh-keyscan` or prefixed in `known_hosts` **must match** the exact string configured in GitHub secret `EC2_HOST`. If `EC2_HOST` contains the instance's public IP, the `known_hosts` entry must match that IP.

---

## Resource Sizing & Memory Planning

Running Neo4j 5.12 (JVM), Redis 7 (In-Memory), and FastAPI (Asynchronous Python) on a single EC2 host requires careful memory allocation:

| Component | Minimum RAM | Recommended RAM | Rationale |
|---|---|---|---|
| **Neo4j 5.12** | 1.5 GB | 2.0 GB | Heap: 512 MB – 1.0 GB; Pagecache: 512 MB for graph traversals. |
| **Redis 7** | 128 MB | 256 MB | Configured with `maxmemory 256mb` and `allkeys-lru` eviction policy. |
| **FastAPI + Uvicorn** | 150 MB | 256 MB | Python 3.11 with 4 Uvicorn workers and connection pool. |
| **OS + Docker Daemon** | 300 MB | 500 MB | Ubuntu Linux baseline, logging, and system daemons. |
| **Total Baseline** | **~2.1 GB** | **~3.0 GB** | |

### Instance Recommendation
- **`t3.micro` (1 GB RAM):** **DO NOT USE.** Neo4j JVM initialization triggers Linux OOM killer and terminates containers.
- **`t3.medium` (2 vCPU, 4 GB RAM):** **RECOMMENDED PRODUCTION SWEET SPOT.** Ample headroom for Neo4j BFS queries and Redis caching without memory pressure. Configured with a 2 GB swap file as an emergency buffer.

---

## Windows / Git Bash Environment Compatibility Notes

When executing AWS CLI commands in **Git Bash on Windows**, two common cross-platform traps occur:

1. **Windows CRLF `\r` Line Endings in Subshells:**
   Native Windows `aws.exe` outputs text with `\r\n`. In Git Bash, running `ACCOUNT_ID=$(aws ...)` retains `\r`, which corrupts variable interpolation (e.g. `BUCKET_NAME="datasets-${ACCOUNT_ID}\r"`).
   $\rightarrow$ **Fix:** Pipe subshell outputs through `tr -d '\r'` in Git Bash:
   ```bash
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text | tr -d '\r')
   ```
2. **File Path Resolution (`file://`):**
   Native `aws.exe` running inside Git Bash does not understand virtual Unix paths like `/tmp/...` or `/c/Users/...`. Passing `file:///tmp/...` causes `aws.exe` to look for `C:\tmp`, which fails with `[Errno 2] No such file or directory`.
   $\rightarrow$ **Fix:** Write rendered policies to the current workspace directory and pass relative paths:
   ```bash
   aws iam put-role-policy ... --policy-document file://rendered-ec2-policy.json
   ```

---

## Step-by-Step AWS Setup Commands (Git Bash & PowerShell)

### Step 1: Amazon S3 (Dataset Storage)

**In Git Bash:**
```bash
AWS_REGION="ap-south-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text | tr -d '\r')
BUCKET_NAME="social-network-datasets-${ACCOUNT_ID}"

# 1. Create Private Bucket
aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$AWS_REGION" \
    --create-bucket-configuration LocationConstraint="$AWS_REGION"

# 2. Enable Server-Side Encryption (AES256)
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# 3. Block All Public Access
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 4. Upload Graph Dataset
aws s3 cp scripts/facebook_combined.txt.gz "s3://${BUCKET_NAME}/datasets/facebook_combined.txt.gz"
```

---

### Step 2: Amazon ECR (Container Registry)

```bash
aws ecr create-repository \
    --repository-name social-network-api \
    --region "$AWS_REGION" \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256
```

---

### Step 3: Amazon CloudWatch (Centralized Logs)

```bash
aws logs create-log-group \
    --log-group-name "/social-network-pathfinding/app" \
    --region "$AWS_REGION"

aws logs put-retention-policy \
    --log-group-name "/social-network-pathfinding/app" \
    --retention-in-days 14 \
    --region "$AWS_REGION"
```

---

### Step 4: AWS IAM (Least-Privilege Roles & Policies)

#### 4.1 EC2 Instance Role & Instance Profile
**In Git Bash:**
```bash
# 1. Create IAM Role for EC2
aws iam create-role \
    --role-name "SocialNetworkEC2InstanceRole" \
    --assume-role-policy-document file://infra/iam/ec2-trust-policy.json

# 2. Render Policy (using '|' delimiter to avoid path conflicts)
sed -e "s|\${AWS_S3_BUCKET}|$BUCKET_NAME|g" \
    -e "s|\${AWS_REGION}|$AWS_REGION|g" \
    -e "s|\${AWS_ACCOUNT_ID}|$ACCOUNT_ID|g" \
    infra/iam/ec2-instance-policy.json > rendered-ec2-policy.json

# 3. Attach Rendered Policy
aws iam put-role-policy \
    --role-name "SocialNetworkEC2InstanceRole" \
    --policy-name "SocialNetworkEC2Policy" \
    --policy-document file://rendered-ec2-policy.json

# Clean up local temporary file
rm -f rendered-ec2-policy.json

# 4. Create and Attach Instance Profile
aws iam create-instance-profile --instance-profile-name "SocialNetworkEC2InstanceProfile"
aws iam add-role-to-instance-profile \
    --instance-profile-name "SocialNetworkEC2InstanceProfile" \
    --role-name "SocialNetworkEC2InstanceRole"
```

#### 4.2 GitHub Actions OIDC Role
Set up OpenID Connect (OIDC) so GitHub Actions authenticates without stored AWS access keys:

```bash
GITHUB_REPO="your-github-username/social-network-pathfinding"

# 1. Create OIDC Provider in AWS (if not already existing)
aws iam create-open-id-connect-provider \
    --url "https://token.actions.githubusercontent.com" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
    "1c5824a9fdac1a70b100777a8468f2135c5c6c66" 2>/dev/null || echo "OIDC provider exists."

# 2. Render Trust Policy
sed -e "s|\${AWS_ACCOUNT_ID}|$ACCOUNT_ID|g" \
    -e "s|\${GITHUB_REPOSITORY}|$GITHUB_REPO|g" \
    infra/iam/github-oidc-trust-policy.json > rendered-github-trust.json

aws iam create-role \
    --role-name "GitHubActionsECRPushRole" \
    --assume-role-policy-document file://rendered-github-trust.json

# 3. Render and Attach Push Policy
sed -e "s|\${AWS_ACCOUNT_ID}|$ACCOUNT_ID|g" \
    -e "s|\${AWS_REGION}|$AWS_REGION|g" \
    infra/iam/github-actions-policy.json > rendered-github-policy.json

aws iam put-role-policy \
    --role-name "GitHubActionsECRPushRole" \
    --policy-name "GitHubActionsECRPushPolicy" \
    --policy-document file://rendered-github-policy.json

rm -f rendered-github-trust.json rendered-github-policy.json
```

---

### Step 5: Amazon EC2 (Host Instance & Security Groups)

```bash
# 1. Get Default VPC ID
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text | tr -d '\r')

# 2. Create Security Group
SG_ID=$(aws ec2 create-security-group \
    --group-name "social-network-ec2-sg" \
    --description "Security group for Social Network API" \
    --vpc-id "$VPC_ID" \
    --query "GroupId" --output text | tr -d '\r')

# 3. Restrict Inbound SSH to your current IP only (Admin access)
MY_IP="$(curl -s https://checkip.amazonaws.com | tr -d '\r')/32"
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$MY_IP"

# 4. Allow Inbound HTTP on Port 80 for Let's Encrypt ACME Challenge & Automatic HTTPS Redirection
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0

# 5. Allow Inbound HTTPS on Port 443 for Encrypted Production Traffic
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0

# NOTICE: Do NOT open port 5000 (FastAPI), 7474/7687 (Neo4j), or 6379 (Redis).
# These ports are unmapped to the host and remain strictly inside Docker's virtual bridge network.

# 5. Fetch Ubuntu 24.04 LTS AMI ID
AMI_ID=$(aws ssm get-parameter \
    --name "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id" \
    --query "Parameter.Value" --output text | tr -d '\r')

KEY_NAME="your-ec2-keypair-name"

# 6. Launch t3.medium Instance
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "t3.medium" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --iam-instance-profile Name="SocialNetworkEC2InstanceProfile" \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=social-network-engine}]' \
    --query "Instances[0].InstanceId" --output text | tr -d '\r')

echo "Launched EC2 instance: $INSTANCE_ID"
```

---

## GitHub Actions CI/CD with OIDC Setup

Configure the following secrets and variables in your GitHub Repository under **Settings > Secrets and variables > Actions**:

### Repository Secrets
| Secret Name | Description | Value Example |
|---|---|---|
| `AWS_ROLE_TO_ASSUME` | The ARN of the GitHubActionsECRPushRole | `arn:aws:iam::123456789012:role/GitHubActionsECRPushRole` |
| `EC2_HOST` | Public IP or DNS of your EC2 instance | `13.233.xx.yy` |
| `EC2_SSH_PRIVATE_KEY` | Private SSH Key contents (`.pem`) used to connect to EC2 | `-----BEGIN RSA PRIVATE KEY-----...` |
| `EC2_SSH_KNOWN_HOSTS` | **Mandatory:** Pinned output of `ssh-keyscan -H <EC2_HOST>` verified via console | `|1|... ssh-ed25519 AAAAC3NzaC1...` |
| `EC2_USER` | EC2 SSH username (Default: `ubuntu`) | `ubuntu` |

### Repository Variables
| Variable Name | Description | Value Example |
|---|---|---|
| `AWS_REGION` | AWS Region for deployment | `ap-south-1` |

---

## Host Provisioning, Healthchecks & Automated Rollback

### 1. Initial Host Setup
SSH into your EC2 instance and run the automated provisioning script:

```bash
ssh -i /path/to/key.pem ubuntu@<EC2_PUBLIC_IP>

# Clone repository
git clone https://github.com/your-username/social-network-pathfinding.git /opt/social-network-pathfinding
cd /opt/social-network-pathfinding

# Run automated setup (Docker Engine, 2GB Swap space, AWS CLI v2)
chmod +x scripts/ec2_setup.sh
./scripts/ec2_setup.sh
```

### 2. Configure Production Secrets (`.env.prod`)
Copy the production environment template and set secure values:

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
nano .env.prod
```

### 3. Deploy Stack with Automated Rollback
Run the deployment script:
```bash
chmod +x scripts/deploy_prod.sh
./scripts/deploy_prod.sh
```

#### How the Automated Healthcheck & Rollback Works:
1. **Pre-Deployment Snapshot:** Before pulling the new image, `deploy_prod.sh` queries `docker inspect` to record the container's current stable image ID (`PREV_IMAGE_ID`).
2. **Upgrade Attempt:** Pulls the new image from ECR and performs `docker compose up -d --remove-orphans`. Downstream database services (`neo4j`, `redis`) remain running without unnecessary restarts.
3. **Internal Health Verification:** Polls internal API health via `docker exec social-network-api-prod curl -s -f http://localhost:5000/health` up to 24 times (every 5 seconds, up to 120 seconds).
4. **Automatic Rollback:** If the new container fails healthcheck or crashes, it automatically tags the previous snapshot as `rollback-target`, recreates only the API container using `docker compose -f docker-compose.prod.yml up -d --pull never api`, verifies recovery over a 50-second loop, and exits with code 1 so the CI pipeline alerts you.
5. **Caddy Reverse Proxy Health:** Confirms Caddy container is running and active on ports 80 and 443.

### 4. Live HTTPS & Certificate Verification (Run After Deployment)

Once the EC2 stack is running and your DNS resolves to the EC2 public IP:

```bash
# 1. Test HTTP to HTTPS automatic redirection (port 80 -> port 443)
curl -I "http://${DOMAIN_NAME}/health"
# Expected response:
# HTTP/1.1 308 Permanent Redirect
# Location: https://${DOMAIN_NAME}/health

# 2. Test live HTTPS response (port 443 with TLS encryption)
curl -i "https://${DOMAIN_NAME}/health"
# Expected response:
# HTTP/2 200
# strict-transport-security: max-age=31536000; includeSubDomains; preload
# x-content-type-options: nosniff
# {"status":"healthy"}

# 3. Inspect the live TLS certificate chain
curl -vI "https://${DOMAIN_NAME}/health" 2>&1 | grep -E "SSL certificate verify ok|subject:|issuer:"
# Expected output:
# *  SSL certificate verify ok.
# *  issuer: C = US, O = Let's Encrypt, CN = R3 (or ZeroSSL)
```

---

## Ongoing Charges After EC2 is Stopped

> [!WARNING]
> When an EC2 instance is **stopped**, compute billing stops ($0.00/hour for the CPU/RAM), but the following auxiliary resources **continue to incur charges**:

1. **EBS Root Volume Storage:**
   - The 30 GB gp3 root volume persists data while the instance is stopped.
   - Cost: **$0.08 per GB-month $\approx$ $2.40 / month**.
2. **Elastic IP Addresses (If Allocated):**
   - If you allocate an Elastic IP and leave it unattached or attached to a stopped instance, AWS charges **$0.005 / hour $\approx$ $3.60 / month**.
   - *Recommendation:* Do **not** allocate an Elastic IP for temporary demonstrations; use the standard public IP assigned at launch.
3. **S3 Object Storage:**
   - Negligible: ~10 MB storage $\approx$ **< $0.05 / month**.
4. **ECR Image Storage:**
   - Container image layers (~400 MB) $\approx$ **$0.04 / month**.
5. **CloudWatch Logs:**
   - Free tier includes 5 GB ingestion and storage. Standard pricing is $0.03/GB-month thereafter. Our 14-day retention policy prevents accumulation.

**Rule of Thumb:** Stopping the EC2 instance reduces ongoing charges from ~$30.39/month down to **~$2.50/month**. To reach **$0.00/month**, execute the [Teardown Procedures](#teardown--cleanup-procedures).

---

## Troubleshooting & Runbook

### 1. CI/CD Fails with "EC2_SSH_KNOWN_HOSTS secret is missing"
- **Cause:** Deployment was attempted without pinning the EC2 host key fingerprint.
- **Fix:** Obtain the verified host key from EC2 console output and add it under GitHub Secrets as `EC2_SSH_KNOWN_HOSTS`.

### 2. Neo4j Fails to Start or Exits with Code 137
- **Cause:** Out of memory (OOM).
- **Remedy:** Verify 2GB swap is enabled (`free -h`). Verify memory limit in `docker-compose.prod.yml` is at least 2048M. Ensure instance is `t3.medium`.

### 3. Ingestion Fails to Download from S3
- **Check IAM Role:** Run `aws sts get-caller-identity` on the EC2 host to verify instance profile is attached.
- **Check S3 permissions:** Run `aws s3 ls s3://$AWS_S3_BUCKET/datasets/` from the EC2 command line.

### 4. Caddy Fails to Obtain TLS Certificate
- **Cause 1: Port 80 Blocked in Security Group.**
  Let's Encrypt requires port 80 open for the ACME HTTP-01 challenge.
  *Remedy:* Ensure port 80 is open to `0.0.0.0/0` in your EC2 Security Group.
- **Cause 2: DNS Resolution Mismatch.**
  The hostname must resolve directly to your EC2 public IP.
  *Remedy:* Run `dig +short "$DOMAIN_NAME"` (or `nslookup "$DOMAIN_NAME"`). If you restarted EC2 and its public IP changed, update `DOMAIN_NAME` in `.env.prod` to match the new IP (e.g. `<NEW_IP>.sslip.io`) and restart Caddy (`docker compose -f docker-compose.prod.yml restart caddy`).
- **Cause 3: Inspect Real-Time ACME Logs.**
  Run `docker compose -f docker-compose.prod.yml logs -f caddy` to observe Caddy's challenge attempts and error messages.

### 5. Caddy Returns 502 Bad Gateway
- **Cause:** The upstream FastAPI container is still initializing or crashed.
- **Remedy:** Check FastAPI logs using `docker compose -f docker-compose.prod.yml logs --tail=50 api`. Verify database connectivity to Neo4j and Redis on `internal-network`.

---

## Teardown & Cleanup Procedures

To ensure you never incur ongoing charges after completing your demonstrations:

```bash
# 1. Stop and terminate EC2 instance (terminates attached EBS volume)
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"

# 2. Delete ECR Repository & container images
aws ecr delete-repository --repository-name social-network-api --force

# 3. Empty and delete S3 bucket
aws s3 rm "s3://${BUCKET_NAME}" --recursive
aws s3api delete-bucket --bucket "$BUCKET_NAME"

# 4. Delete CloudWatch Log Group
aws logs delete-log-group --log-group-name "/social-network-pathfinding/app"

# 5. Remove IAM roles & policies
aws iam delete-role-policy --role-name "SocialNetworkEC2InstanceRole" --policy-name "SocialNetworkEC2Policy"
aws iam remove-role-from-instance-profile --instance-profile-name "SocialNetworkEC2InstanceProfile" --role-name "SocialNetworkEC2InstanceRole"
aws iam delete-instance-profile --instance-profile-name "SocialNetworkEC2InstanceProfile"
aws iam delete-role --role-name "SocialNetworkEC2InstanceRole"

aws iam delete-role-policy --role-name "GitHubActionsECRPushRole" --policy-name "GitHubActionsECRPushPolicy"
aws iam delete-role --role-name "GitHubActionsECRPushRole"

# 6. Delete Security Group
aws ec2 delete-security-group --group-id "$SG_ID"
```
