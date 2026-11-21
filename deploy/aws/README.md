# AWS Demonstration Deployment Runbook

This directory contains the deployment kit, IAM policies, Compose overlays, and operational scripts for the single-host AWS demonstration. The deployment was verified in `ap-southeast-2` on Ubuntu 24.04 / `m7i-flex.large`. The EC2 instance is currently **stopped, not terminated**; the application is offline. The previously verified HTTPS endpoint was `https://3.25.91.158.sslip.io/`, but the public IP can change after a stop/start.

---

## 1. Architecture Overview

- **Host:** Single EC2 instance running **Ubuntu 24.04** (the configured environment uses `m7i-flex.large`, 8 GiB RAM).
- **Network Ingress:** EC2 security group allows HTTP and HTTPS and restricts SSH. Caddy terminates HTTPS. API, Neo4j and Redis are not published publicly.
- **Durable State:** Compose named volumes on the EC2 host store Neo4j and monitoring data. An S3 bucket is configured for graph backups; this documentation does not assert an unverified backup schedule, retention period, or restore test.
- **Logging & Monitoring:** `deploy/aws/docker-compose.aws.yml` configures Docker's `awslogs` driver for API, Caddy, Neo4j and Redis to `/pathfinding-demo` in `ap-southeast-2`. CloudWatch Agent was not installed. Prometheus and Grafana run under the Compose `monitoring` profile and bind to host loopback only.
- **Identity & Security:** The EC2 instance used role `graph-project-ec2-role`. Do not put credentials or secret values in documentation.

The running deployment returned `HTTP/2 200` and `{"status":"ok"}` from its health endpoint. CloudWatch Live Tail showed fresh application logs; Logs Insights queries ran successfully and visualizations were created for requests/minute, average API latency, status codes, most-used endpoints and pathfinding activity. Prometheus was healthy, with both configured scrape targets `UP`; Grafana reported database status `ok` and served the provisioned dashboard `Social Network API Observability`. These are historical verification results from when the instance was running.

## 2. Resume the stopped instance

Start the existing EC2 instance from the EC2 console in `ap-southeast-2` (or use the approved operator workflow for that account). Wait for EC2 status checks to pass, then retrieve its current public IPv4 address from the console. A stop/start can assign a different public IP; do not rely on the old address or old sslip.io URL. Reconnect with the current address:

```bash
ssh -i /path/to/<KEY_PAIR_NAME>.pem ubuntu@<CURRENT_PUBLIC_IP>
cd social-network-pathfinding
```

If SSH is denied, confirm the current client IP is still allowed by the restricted SSH security-group rule. Refresh any DNS or sslip.io URL references for the new IP. Starting EC2 incurs compute charges; stopping it later stops compute charges, but attached EBS storage and retained AWS services may continue to incur charges.

## 3. Start the production Compose stack

Use the existing private `.env` on the instance. Do not replace it with the example if it contains the deployment's configured values. The example documents `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml:deploy/aws/docker-compose.aws.yml` and `COMPOSE_PROFILES=edge`; Compose loads that file selection and the AWS `awslogs` overlay. Preserve all secret values privately.

```bash
docker compose config -q
docker compose up -d --build
docker compose ps
curl -fsS https://<CURRENT_HOSTNAME_OR_IP>/health
curl -fsS https://<CURRENT_HOSTNAME_OR_IP>/health/ready
BASE_URL=https://<CURRENT_HOSTNAME> bash deploy/aws/scripts/verify.sh
```

For the IP-based HTTPS hostname, use the currently valid hostname/certificate setup from the instance; the former `3.25.91.158.sslip.io` address is historical. If readiness fails, inspect `docker compose logs --tail=100 api neo4j redis caddy`. Do not use `down -v`: it deletes named data volumes.

### Enable Prometheus and Grafana

The Compose file already publishes Prometheus on `127.0.0.1:9090` and Grafana on `127.0.0.1:3000`. Set non-placeholder `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` in the existing `.env` only if they are not already configured, then start the monitoring profile:

```bash
docker compose --profile monitoring up -d
docker compose ps prometheus grafana
```

The configured `edge` profile remains enabled by `.env`. Prometheus scrapes its own target and `api:5000/metrics`; the API `/metrics` endpoint is reached on the private Compose network.

From a local terminal, open an SSH tunnel using the current EC2 address:

```bash
ssh -i /path/to/<KEY_PAIR_NAME>.pem -N \
  -L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000 \
  ubuntu@<CURRENT_PUBLIC_IP>
```

Then browse to `http://127.0.0.1:9090` (Prometheus) and `http://127.0.0.1:3000` (Grafana). These services are not publicly exposed. Grafana provisions `Social Network API Observability` with request rate, HTTP error rate, latency percentiles, path cache hit ratio and Neo4j query latency p95.

## 4. CloudWatch logs and queries

The AWS overlay assigns Docker's `awslogs` driver to API, Caddy, Neo4j and Redis, using region `AWS_REGION` and group `CW_LOG_GROUP` (default `/pathfinding-demo`). The driver uses non-blocking mode and a 4 MiB buffer. The instance role needs the log-stream write permissions defined for the existing log group. The CloudWatch Agent is not part of this setup.

In the CloudWatch console, select `ap-southeast-2` and **Logs > Live Tail**, then select `/pathfinding-demo` to watch fresh container output. In **Logs Insights**, select the same group and a relevant time range. API request logs are JSON with `message`, `route`, `status`, and `duration_ms`; example queries:

```text
fields @timestamp, route, status, duration_ms
| filter message = "http_request"
| sort @timestamp desc
| limit 100
```

```text
fields @timestamp, route, status, duration_ms
| filter message = "http_request"
| stats count(*) as requests by bin(1m)
```

```text
fields route, status, duration_ms
| filter message = "http_request"
| stats avg(duration_ms) as avg_latency_ms by route
| sort avg_latency_ms desc
```

```text
fields status
| filter message = "http_request"
| stats count(*) as responses by status
| sort status asc
```

```text
fields @timestamp, route, status
| filter message = "http_request" and route like /\/api\/v1\/path\//
| stats count(*) as path_requests by bin(1m)
```

Use Logs Insights **Visualization** to chart the time-binned request query, average latency, grouped status codes, endpoint counts, and path-request activity. CloudWatch dashboard widgets created during the deployment included requests/minute, average latency, HTTP status codes, most-used endpoints and pathfinding activity. Queries execute over retained log events; no retention duration is asserted here.

---

## 5. Historical provisioning notes

Older launch checklists and initial HTTP-only instructions are superseded by the current-state runbook above. Do not use them to recreate resources, replace the instance environment, or change security groups. For a new host, first reconcile the existing AWS account resources and the current `deploy/aws/env.aws.example`, Compose overlays, and bootstrap script; this guide is for resuming the retained deployment.

---

## 6. Operational scripts and data safety

- **`deploy/aws/scripts/bootstrap-ec2.sh`**: Installs Docker Engine, Compose v2, Git, jq, AWS CLI, and configures swap only on hosts with at most 2 GiB RAM. Supports Ubuntu 24.04.
- **`deploy/aws/scripts/backup-to-s3.sh`**: Uploads one identified dump and verifies downloaded S3 object bytes against SHA-256.
- **`deploy/aws/scripts/restore-from-s3.sh <UTC_TIMESTAMP>`**: Downloads exactly one dump for the timestamp, verifies it, and requires explicit confirmation before replacing current graph data.
- **`deploy/aws/scripts/verify.sh`**: Set `GRAPH_START_ID` and `GRAPH_END_ID` to known connected dataset nodes to check pathfinding and cache; otherwise these checks are reported as skipped. Rate-limit probing is opt-in with `--test-rate-limit`.

Backup and restore use `DOCKER_SUDO=auto` by default. Set it to `never` to require direct Docker socket access or `always` to use non-interactive `sudo -n docker`; the scripts do not change socket permissions. Restore is supported only for backups made with the current dump, SHA-256, and Neo4j-version metadata sidecars. Older backups without version metadata are intentionally rejected because compatibility cannot be validated safely. The restore script targets the Compose application database `neo4j`; it does not provide an isolated/test target. Use a separately configured Compose project and data volume for restore drills.

### IAM notes

The supplied instance policy grants `CreateLogStream` and `PutLogEvents` for the pre-created `/pathfinding-demo` log group. The log group must already exist. These permissions cover the Docker `awslogs` driver; the example does not install or run the CloudWatch Agent. If host metrics from `iam/cloudwatch-agent-config.json` are later enabled, review and attach a separate least-privilege CloudWatch Agent policy for `cloudwatch:PutMetricData` and any EC2 metadata discovery actions required by that agent configuration. Keep those permissions separate from container logging. The EC2 role does not grant metric-reading actions: the operator or monitoring identity that queries metrics needs `cloudwatch:GetMetricStatistics` (and, if it discovers metric names dynamically, `cloudwatch:ListMetrics`). The historical missing `GetMetricStatistics` finding belongs to that reader identity and does not justify broadening the instance logging policy.

---

To stop the application safely while keeping its data, stop the Compose services without removing volumes, then stop the EC2 instance from the console:

```bash
docker compose stop
```

Stopping EC2 reduces compute charges but does not remove the EBS volume, S3 backups, CloudWatch log group, or IAM role. Preserve the instance and named volumes if you expect to resume. Do not run `docker compose down -v`, remove volumes, or terminate EC2 as a cost-saving step. Backups are handled explicitly by `deploy/aws/scripts/backup-to-s3.sh`; a restore replaces the application graph database and requires confirmation. No backup schedule, retention period, or successful restore test is asserted here.

## 7. Safe shutdown and cleanup

Cleanup is a separate, explicitly approved operation. The existing EC2 instance, IAM role, CloudWatch log group, S3 bucket, and backup objects must be reviewed individually; do not apply the generic deletion checklist to shared or retained resources.
