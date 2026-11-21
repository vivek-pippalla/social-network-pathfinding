# AWS Resources Inventory & Lifecycle Notes

This is a preservation-oriented inventory for the existing demonstration deployment. The EC2 instance is stopped, not terminated. Do not treat this list as authorization to modify or delete resources.

| Resource | Known details | Current handling |
|---|---|---|
| EC2 instance | Ubuntu 24.04, `m7i-flex.large`, `ap-southeast-2` | Stopped; not terminated. Start only through the existing AWS account workflow. |
| EC2 public address | Previously `3.25.91.158`, used with sslip.io | May change after stop/start. Retrieve the current address from the EC2 console before reconnecting. |
| EC2 storage / Compose volumes | Holds persistent application and monitoring data | Preserve. Exact size, type and delete-on-termination setting are not confirmed here. |
| Security group | HTTP and HTTPS; restricted SSH | Preserve current rules. Exact source CIDRs are not recorded in this document. |
| IAM instance role | `graph-project-ec2-role` | Preserve; do not replace its policies based on template files. |
| S3 backup bucket | `graph-project-backups-unique-number` in `ap-southeast-2` | Preserve bucket and every object. Backup schedule, retention and restore success are not established here. |
| CloudWatch Logs group | `/pathfinding-demo` in `ap-southeast-2` | Preserve. Retention period is not confirmed here. |
| Prometheus / Grafana | Compose `monitoring` profile; loopback-bound ports | Persistent data is on Compose volumes. Use SSH tunnels; do not expose publicly. |

Stopping EC2 avoids instance compute while stopped, but attached EBS and retained AWS services can continue to incur charges. Review the AWS billing console for current costs. Do not terminate the instance or remove volumes as a cost-saving shortcut when preserving this deployment's data.
