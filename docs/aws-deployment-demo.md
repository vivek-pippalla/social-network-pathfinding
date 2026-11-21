# AWS Demonstration Deployment & Verification Record

This record captures the operator-provided deployment facts and verification results for the AWS demonstration. The runbook is maintained in [`deploy/aws/README.md`](../deploy/aws/README.md).

## Current status

- The EC2 instance in `ap-southeast-2` is **stopped, not terminated**. The application is currently offline.
- The deployment used Ubuntu 24.04, instance type `m7i-flex.large`, FastAPI, Neo4j, Redis, Caddy and Docker Compose.
- The previously used HTTPS endpoint was `https://3.25.91.158.sslip.io/`. Its health endpoint returned `HTTP/2 200` and `{"status":"ok"}` while the instance was running. The address may change after restart; this endpoint must not be presented as currently available.
- The deployment used EC2 role `graph-project-ec2-role`, S3 graph-backup bucket `graph-project-backups-unique-number`, CloudWatch Logs group `/pathfinding-demo`, and a security group with HTTP/HTTPS ingress and restricted SSH.
- No credentials or secret environment values are recorded here.

## Verified deployment and monitoring

| Area | Recorded result |
|---|---|
| HTTPS health | Returned HTTP/2 200 and `{"status":"ok"}` while running. |
| Docker logging | `awslogs` overlay sent API, Caddy, Neo4j and Redis container logs to `/pathfinding-demo` in `ap-southeast-2`. CloudWatch Live Tail displayed fresh application logs. CloudWatch Agent was not installed. |
| CloudWatch Logs Insights | Queries executed successfully. Visualizations created for API requests per minute, average API latency, HTTP status codes, most-used API endpoints and pathfinding activity. |
| Prometheus | Started with the Compose monitoring profile, accessed through an SSH tunnel, health endpoint healthy; Prometheus self-monitoring and API scrape targets were both `UP`. API metrics were collected from `/metrics`. |
| Grafana | Started with the monitoring profile and accessed through an SSH tunnel. Health endpoint reported database status `ok`; provisioned dashboard was `Social Network API Observability`. |
| Grafana panels | Request rate, HTTP error rate, HTTP latency percentiles, path cache hit ratio and Neo4j query latency p95. |

Prometheus and Grafana were bound to host loopback by the Compose configuration and were not publicly exposed. Dashboard query definitions are in [`monitoring/grafana/dashboards/sample-dashboard.json`](../monitoring/grafana/dashboards/sample-dashboard.json).

## Not established by this record

The EC2 host was stopped after verification. No claim is made here that the service is currently reachable. The exact current public IP, EBS volume size/type and deletion behavior, CloudWatch retention period, S3 lifecycle/backup schedule, or a successful restore drill are not confirmed by the supplied deployment evidence. The existence of the backup bucket does not by itself establish that a current backup is available or restorable. Check the AWS console and the actual objects before relying on recovery.

No automatic teardown is authorized by this document. Preserve the stopped instance, attached data volumes, IAM role, log group, bucket and all existing backup objects unless a separately reviewed operation explicitly authorizes a change.
