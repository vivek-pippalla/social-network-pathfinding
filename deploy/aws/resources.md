# AWS Resources Inventory & Lifecycle Tracking

This inventory tracks all AWS resources utilized during the Phase 15 single-instance demonstration deployment.

| Resource | Name / Tag | Created In | Billable Mode | Action at Cleanup |
|---|---|---|---|---|
| **EC2 Instance** | `pathfinding-demo`<br/>`Project=pathfinding-demo` | 15.4 Step 1 | Hourly compute while running; public IPv4 (~$0.005/hr) | Terminate (stops compute & releases IPv4) |
| **EBS Root Volume** | 20 GiB gp3<br/>`Project=pathfinding-demo` | 15.4 Step 1 | **Per GB-month while running AND while stopped** | Automatically deleted on instance termination (*Delete on termination: true*); verify volume deletion |
| **Security Group** | `pathfinding-demo-sg`<br/>`Project=pathfinding-demo` | 15.3 P9 | Free | Delete after instance termination |
| **EC2 Key Pair** | `<KEY_PAIR_NAME>` | 15.3 P7 | Free | Delete key pair; delete local `.pem` file |
| **IAM Instance Role & Profile** | `pathfinding-demo-ec2-role` | 15.3 P6 | Free | Delete role, attached inline policy, and instance profile |
| **Amazon S3 Bucket** | `<BUCKET_NAME>`<br/>`Project=pathfinding-demo` | 15.3 P4 | Minimal (standard storage and request tier) | Empty with `aws s3 rm --recursive` then delete bucket |
| **CloudWatch Log Group** | `/pathfinding-demo`<br/>(7-day retention) | 15.3 P5 | Ingestion beyond allowance; 7-day retention | Delete log group |
| **AWS Budget** | Monthly cost budget ($10 ceiling) | 15.2 Step 4 | Free (within first 2 action budgets) | Retain as ongoing account safety guardrail or delete |
| **IAM OIDC Provider & Role (Optional)** | `token.actions.githubusercontent.com` | 15.9 | Free | Delete if GitHub Actions packaging workflow was configured |
