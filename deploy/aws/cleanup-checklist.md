# Phase 15 AWS Cleanup & Decommissioning Checklist

Execute this checklist manually item by item immediately upon completing demonstration evidence capture. No resources should remain running.

---

## 1. Save Gate Verification (Mandatory Before Any Deletion)

Do not delete any cloud resources until all of the following conditions are satisfied:

- [ ] All smoke and feature verification test results are recorded with dates in `docs/aws-deployment-demo.md`.
- [ ] All 12 demonstration screenshots are saved in `docs/images/aws/` and personal IPs / account IDs are redacted.
- [ ] Demonstration video link is recorded in `docs/aws-deployment-demo.md` (if video was recorded).
- [ ] A final S3 backup dump has been downloaded locally if data retention is desired.
- [ ] All local template files and deployment scripts are committed.

---

## 2. Resource Teardown Checklist

Perform these steps in order using the AWS Console or AWS CLI. Verify each resource by its tag: `Project=pathfinding-demo`.

| # | Resource | Action / Verification Command | Done |
|---|---|---|---|
| **1** | **EC2 Instance** | Terminate instance in the console, or:<br/>`aws ec2 terminate-instances --instance-ids <INSTANCE_ID> --region <REGION>`<br/>*Wait until status is `terminated`.* | [ ] |
| **2** | **EBS Volumes** | Verify root volume is deleted:<br/>`aws ec2 describe-volumes --region <REGION> --filters Name=tag:Project,Values=pathfinding-demo`<br/>*Ensure no available volumes remain.* | [ ] |
| **3** | **EBS Snapshots** | Verify no lingering snapshots:<br/>`aws ec2 describe-snapshots --owner-ids self --region <REGION>` | [ ] |
| **4** | **Amazon S3** | Empty and delete bucket:<br/>`aws s3 rm s3://<BUCKET_NAME> --recursive`<br/>`aws s3 rb s3://<BUCKET_NAME>` | [ ] |
| **5** | **CloudWatch Logs** | Delete log group:<br/>`aws logs delete-log-group --log-group-name /pathfinding-demo --region <REGION>` | [ ] |
| **6** | **Security Group** | Delete security group (after EC2 termination completes):<br/>`aws ec2 delete-security-group --group-id <SG_ID> --region <REGION>` | [ ] |
| **7** | **Key Pair** | Delete EC2 key pair and remove local `.pem` file:<br/>`aws ec2 delete-key-pair --key-name <KEY_PAIR_NAME> --region <REGION>` | [ ] |
| **8** | **Elastic IPs** | Confirm no Elastic IPs were allocated:<br/>`aws ec2 describe-addresses --region <REGION>` *(must be empty)* | [ ] |
| **9** | **IAM Resources** | Delete instance profile, instance role, and inline policies. | [ ] |
| **10** | **GitHub Environment** | Remove any repository variables in GitHub `aws-demo` environment if used. | [ ] |
| **11** | **Other Regions** | Check EC2 dashboard to confirm no instances were created in other regions. | [ ] |

---

## 3. Post-Cleanup Billing Verification

1. Open **Billing and Cost Management** -> **Cost Explorer**.
2. Confirm running EC2 instance hours drop to zero.
3. Check Cost Explorer again **48 hours after cleanup** to account for cloud billing latency.
4. Record final billing evidence in `docs/aws-deployment-demo.md`.
