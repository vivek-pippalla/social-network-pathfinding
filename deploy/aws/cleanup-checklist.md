# AWS Shutdown & Preservation Checklist

The current EC2 instance is stopped, not terminated. This checklist covers routine cost-saving shutdown while preserving the deployment. It does not authorize deleting AWS resources or data.

## Stop the application while keeping its data

If the instance is running and the application should be paused, connect to the host and run:

```bash
docker compose stop
```

Then stop the existing instance in the EC2 console in `ap-southeast-2`. Do not terminate it. Do not run `docker compose down -v`, remove Compose volumes, delete the EBS volume, empty the S3 bucket, or delete the CloudWatch log group. Stopping EC2 avoids compute charges while stopped, but attached storage and other retained AWS services may continue to incur charges.

## Resume

Start the existing instance from the EC2 console, wait for status checks, then look up its current public IP. A stop/start can assign a new IP. See [`README.md`](README.md#2-resume-the-stopped-instance) for SSH, stack startup, health checks and monitoring access.

## Before any separately authorized decommissioning

Review each exact resource in the AWS console and identify its data and billing impact. Confirm independently that any desired backups exist and are usable; a bucket's existence does not prove a successful backup or restore. Preserve `graph-project-ec2-role`, `/pathfinding-demo`, `graph-project-backups-unique-number`, all S3 objects and any storage containing needed Compose volumes unless the user explicitly authorizes deletion of those specific resources. This checklist contains no termination or deletion commands.
