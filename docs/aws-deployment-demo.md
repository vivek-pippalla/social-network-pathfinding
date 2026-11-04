# AWS Demonstration Deployment & Evidence Record

This document records the design, cost envelope, verification procedures, and observed results for the single-instance AWS demonstration deployment of **Social Network Pathfinding Engine** (`social-network-pathfinding`).

> [!IMPORTANT]
> **Status: PENDING (Phase 15 Part A Skeleton)**
> All live AWS verification checks, screenshots, and billing records in this document are currently **PENDING**. Live deployment and manual evidence capture occur in Phase 15 Parts B and C after repository merge/tagging. No live AWS resources are active during Part A.

---

## 1. Architectural Overview

The AWS demonstration runs on a single Amazon EC2 instance (Amazon Linux 2023) within a default VPC in region `<REGION>` (e.g., `ap-south-1` or `us-east-1`). No database ports, cache ports, or backend ports are exposed to the public internet.

```mermaid
graph TD
    subgraph Client["Operator / Browser"]
        ClientIP["Allowed IP (/32)<br/>Operator Machine"]
    end

    subgraph AWS["AWS Cloud (Region: <REGION>)"]
        subgraph SecurityGroup["Security Group (Strict /32 Inbound)"]
            Port22["TCP 22 (SSH Admin)"]
            Port80["TCP 80 (HTTP / Caddy)"]
        end

        subgraph EC2["EC2 Instance (Amazon Linux 2023)"]
            IAMRole["EC2 Instance IAM Role<br/>(No Long-Lived Keys)"]
            Caddy["Caddy (Reverse Proxy)<br/>:80 Ingress"]
            API["FastAPI API (Port 8000)<br/>Internal Only"]
            Neo4j["Neo4j 5.26-community<br/>Bolt :7687 Internal Only"]
            Redis["Redis 7-alpine<br/>:6379 Internal Only"]

            Caddy -->|/api/*, /health*| API
            Caddy -->|/* (Static)| Caddy
            API -->|Graph Queries| Neo4j
            API -->|Path & Query Cache| Redis
        end

        subgraph Managed["Managed AWS Services"]
            S3["Amazon S3 Bucket<br/>s3://<BUCKET_NAME>/backups/<br/>s3://<BUCKET_NAME>/artifacts/"]
            CloudWatch["CloudWatch Logs Group<br/>/pathfinding-demo<br/>(Retention: 7 days)"]
        end

        IAMRole -.->|PutObject / GetObject| S3
        EC2 -.->|awslogs driver (non-blocking)| CloudWatch
    end

    ClientIP -->|SSH Only| Port22
    ClientIP -->|HTTP Only| Port80
```

### Key Architectural Decisions

1. **Single-Instance Deployment:** Minimal demo footprint using Docker Compose with local volume mounts (`neo4j-data`, `redis-data`, `caddy-data`). Avoids high-cost managed services (RDS, ElastiCache, Neo4j Aura).
2. **Reverse Proxy Edge:** Caddy handles reverse proxying on port 80, blocking operational endpoints (`/metrics`, `/docs`) from unauthorized access.
3. **Internal-Only Databases:** Neo4j (7474, 7687) and Redis (6379) are bound strictly inside the Docker bridge network. No database ports are published or mapped to the host.
4. **Least-Privilege Instance IAM Role:** Uses AWS STS temporary credentials via IMDSv2. No IAM access keys or credentials are stored on the instance disk or in `.env`.
5. **Non-Blocking CloudWatch Logging:** Containers log via the `awslogs` driver in `mode: non-blocking` with a `max-buffer-size: 4m`, ensuring logging backpressure cannot impact API availability.
6. **Encrypted S3 Backups with Expiration:** Neo4j offline backups are compressed, hashed with SHA-256, and stored in S3 under `backups/` with a 14-day lifecycle expiration rule.

---

## 2. Decision Record & Cost Safeguards

### Deployment Decision Record

| Parameter | Planned Demonstration Value | Actual Value | Notes |
| :--- | :--- | :--- | :--- |
| **AWS Region** | `<REGION>` | PENDING | e.g., `ap-south-1` or `us-east-1` |
| **Instance Type** | `t3.small` / `t3.medium` (or free-tier eligible `t4g.small` / `t2.micro` with swap) | PENDING | Memory sizing requirement: ~1.2 GiB working set |
| **AMI** | Amazon Linux 2023 Minimal (`al2023-ami-minimal-*`) | PENDING | Includes AWS CLI v2 and systemd |
| **Root Volume** | 20 GiB gp3 EBS (encrypted) | PENDING | Adequate for Docker images, dataset, and swapfile |
| **Hourly Rate** | ~$0.0208 / hour (`t3.small` in `ap-south-1`) | PENDING | Plan for 12–16 total running hours (~$0.35 total) |
| **Budget Ceiling** | $10.00 / month with email alert at 50% ($5.00) | PENDING | Pre-launch cost guardrail |
| **Target Commit** | `v1.0.0` release tag | PENDING | Tagged commit SHA |

---

## 3. Verification Test Checklists

### A. Smoke Test Checklist (S1–S13)

| ID | Check | How | Expected | Result | Date | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **S1** | Instance healthy | Console status checks; SSH works | 2/2 checks passed; SSH succeeds | PENDING | - | - |
| **S2** | Tooling present | `docker compose version`, `aws sts get-caller-identity` | Tooling functional; caller identity is instance IAM role | PENDING | - | - |
| **S3** | All services up | `docker compose ps` | `api`, `neo4j`, `redis`, `caddy` running/healthy; monitoring absent | PENDING | - | - |
| **S4** | Liveness | `curl -fsS http://localhost/health` | HTTP 200 `{"status":"ok"}` | PENDING | - | - |
| **S5** | Readiness | `curl -fsS http://localhost/health/ready` | HTTP 200, `database: ok`, `cache: ok` | PENDING | - | - |
| **S6** | Public reachability | From laptop: `curl -fsS http://<PUBLIC_IP>/health` | HTTP 200 | PENDING | - | - |
| **S7** | Frontend loads | Browser `http://<PUBLIC_IP>/` | UI loads cleanly; only same-origin requests | PENDING | - | - |
| **S8** | Neo4j connectivity | Cypher shell query for node count | Returns count of dataset users (4,039) | PENDING | - | - |
| **S9** | Redis connectivity & auth | `redis-cli -a "$REDIS_PASSWORD" ping` | Authenticated returns `PONG`; unauthenticated returns `NOAUTH` | PENDING | - | - |
| **S10** | Closed ports | From alternate network (e.g. mobile hotspot): probe 22, 80, 7474, 7687, 6379, 8000 | All ports timed out or refused | PENDING | - | - |
| **S11** | Operational endpoints | `curl -s -o /dev/null -w '%{http_code}' http://<PUBLIC_IP>/metrics` and `/docs` | `/metrics` blocked (403/404); `/docs` 404 | PENDING | - | - |
| **S12** | CloudWatch Logs | AWS Console: `/pathfinding-demo` log group | Log streams present per container with recent events | PENDING | - | - |
| **S13** | Memory headroom | `free -m`, `docker stats --no-stream`, `sudo dmesg \| grep -i killed` | No OOM kills; swap usage stable | PENDING | - | - |

---

### B. Feature Verification Checklist (F1–F12)

| ID | Feature | How | Expected | Result | Date | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **F1** | Ingestion | `MATCH (u:User {source:'snap'}) RETURN count(u)`; re-run ingest | 4,039 nodes, 88,234 edges; rerun is idempotent | PENDING | - | - |
| **F2** | Auth journey | Register, token, me endpoint; unauthenticated access | Token issued; me returns email; unauthenticated returns 401 envelope | PENDING | - | - |
| **F3** | Public profile & search | `GET /api/v1/users/{id}`, `GET /api/v1/users/search?q=` | Returns `id`, `name`, `source` only; no email or password hash | PENDING | - | - |
| **F4** | Friendship operations | Add, list, remove; idempotent add/remove; add self; add unknown | 201 then 200 `created:false`; self 400 `CANNOT_FRIEND_SELF`; unknown 404 | PENDING | - | - |
| **F5** | Mutual friends | `GET /api/v1/users/{id}/mutual` vs direct Cypher calculation | API mutual friend list and count match Cypher ground truth | PENDING | - | - |
| **F6** | Shortest path | 10 benchmark pairs; reversed pair; same user; unknown user | Same hop counts as local Phase 14 record; symmetric; same user 0 hops | PENDING | - | - |
| **F7** | Friend suggestions | `GET /api/v1/suggestions/me` twice | Deterministic ordering; excludes self and existing friends | PENDING | - | - |
| **F8** | Cache behaviour | Query same path twice; add bridging friendship; remove friendship | 1st `cached:false`, 2nd `cached:true`; invalidates after graph mutation | PENDING | - | - |
| **F9** | Auth surface | `POST /api/v1/connections`, `POST /api/v1/users/` | Returns 404 / 405 (legacy unauthenticated routes removed) | PENDING | - | - |
| **F10** | Rate limiting | 6 failing login attempts within 60s window | 6th attempt returns 429 with `Retry-After`; real client IP recognized | PENDING | - | - |
| **F11** | Uniform error envelope | Malformed request, invalid ID | Uniform JSON error with `request_id`; correlation ID found in CloudWatch | PENDING | - | - |
| **F12** | UI journey | Browser walkthrough: register, search, pathfind, inspect graph | Frontend renders without console errors or external CDN leaks | PENDING | - | - |

---

### C. Persistence & Recovery Tests (P1–P6)

| ID | Test | Procedure | Expected | Result | Date | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **P1** | Container restart | `docker compose restart`, poll `/health/ready` | Services recover healthy; registered user can still log in | PENDING | - | - |
| **P2** | Stack down and up | `docker compose down` (without `-v`), then `docker compose up -d` | Data volumes intact; node and edge counts unchanged | PENDING | - | - |
| **P3** | Host reboot | `sudo reboot`, reconnect over SSH | Systemd restarts Docker; stack auto-starts with data intact | PENDING | - | - |
| **P4** | Instance stop/start | Console: Stop, then Start | EBS volume reattached; services recover on new public IP | PENDING | - | - |
| **P5** | S3 backup | `deploy/aws/scripts/backup-to-s3.sh` | Dump and `.sha256` uploaded under `backups/`; checksum verified | PENDING | - | - |
| **P6** | S3 restore drill | Destroy volume with `docker compose down -v`, restore from S3 | Data restored cleanly; node/edge counts match pre-destruction counts | PENDING | - | - |

---

### D. Failure Drills (D1–D4)

| ID | Drill | Procedure | Expected | Result | Date | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **D1** | Redis degraded mode | `docker compose stop redis` | Pathfinding falls back to Neo4j (200 OK, `cached:false`); login 503; `/health/ready` 200 degraded | PENDING | - | - |
| **D2** | Neo4j outage | `docker compose stop neo4j` | Data endpoints return 503 `UNAVAILABLE`; `/health/ready` 503; recovers on start | PENDING | - | - |
| **D3** | CloudWatch logging backpressure | Temporarily revoke `logs:PutLogEvents` permission | API remains responsive (non-blocking logging mode); logs buffer without crash | PENDING | - | - |
| **D4** | Host interruption | Terminate or reboot during request loop | Stack recovers cleanly on boot without database corruption | PENDING | - | - |

---

### E. Security Verification (X1–X6)

| ID | Check | Procedure | Expected | Result | Date | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **X1** | Security group inbound | AWS Console / CLI `describe-security-groups` | Only TCP 22 and 80 allowed, strictly restricted to operator `/32` | PENDING | - | - |
| **X2** | IMDSv2 enforcement | `aws ec2 describe-instances --query '...MetadataOptions'` | `HttpTokens: required`, `HttpPutResponseHopLimit: 2` | PENDING | - | - |
| **X3** | No stored credentials | `ls -la ~/.aws/`, `aws sts get-caller-identity` | No AWS credentials file; caller is the attached instance IAM role | PENDING | - | - |
| **X4** | S3 least privilege | Attempt `aws s3 cp /etc/hostname s3://<BUCKET_NAME>/disallowed.txt` | Access Denied (role only permits `backups/` write and `artifacts/` read) | PENDING | - | - |
| **X5** | CloudWatch log redaction | Search log group for passwords, JWT tokens, `Authorization` | Zero plaintext credentials or tokens in log streams | PENDING | - | - |
| **X6** | Host permissions & status | `stat -c '%a' .env`, `git status` on instance | `.env` is `600`; `.env` is not tracked in Git; working tree clean | PENDING | - | - |

---

## 4. Teardown & Resource Cleanup Record

| Resource | Action Required | Verification Command / Console Check | Status | Verification Date |
| :--- | :--- | :--- | :--- | :--- |
| **EC2 Instance** | Terminate instance | `aws ec2 describe-instances --filters Name=tag:Project,Values=social-network-pathfinding` (state: terminated) | PENDING | - |
| **EBS Volumes** | Delete attached gp3 volume | `aws ec2 describe-volumes --filters Name=tag:Project,Values=social-network-pathfinding` (empty) | PENDING | - |
| **Security Group** | Delete demo security group | `aws ec2 describe-security-groups --group-names pathfinding-demo-sg` (not found) | PENDING | - |
| **S3 Bucket** | Empty and delete bucket | `aws s3 ls s3://<BUCKET_NAME>` (NoSuchBucket) | PENDING | - |
| **CloudWatch Log Group** | Delete log group | `aws logs describe-log-groups --log-group-name-prefix /pathfinding-demo` (empty) | PENDING | - |
| **IAM Role & Policies** | Detach and delete role/policies | `aws iam get-role --role-name PathfindingEC2InstanceRole` (NoSuchEntity) | PENDING | - |
| **OIDC Provider / Role** | Delete OIDC role (if used) | `aws iam get-role --role-name PathfindingGitHubActionsRole` (NoSuchEntity) | PENDING | - |
| **48-Hour Billing Audit** | Recheck AWS Billing Console | Cost Explorer shows zero running charges for demo resources | PENDING | - |

---

## 5. Known Limitations & Demonstration Trade-Offs

1. **HTTP Ingress (No Domain / No ACME):** To keep the demonstration self-contained and cost-free, the deployment runs plain HTTP on port 80 restricted to the operator's `/32` IP address. Automatic HTTPS via ACME requires a registered public domain name and unrestricted port 80 ingress, which is intentionally avoided.
2. **Single Host (No High Availability):** All services (FastAPI, Neo4j, Redis, Caddy) run on a single EC2 instance. This tests memory footprint and operational simplicity, but does not provide multi-AZ failover.
3. **Ephemeral Demonstration Lifespan:** The deployment is designed to be provisioned, verified, recorded, and immediately torn down within 12–16 running hours to eliminate ongoing cloud costs.
