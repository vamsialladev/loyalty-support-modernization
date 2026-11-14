# Teardown and cost warnings

DEL-06; ADR-0085. **Nothing in this repository has created a paid resource.** This page is for whoever, with the
owner's approval, someday applies the AWS Terraform or creates the demo host.

## AWS reference path (`infrastructure/terraform/aws/`)
**It costs money from the moment it's applied**, even with no traffic. Estimate before applying: about $100 a month
or more at the smallest sizes, mostly the NAT gateway, the load balancer, Fargate and RDS (an estimate, option F in
`docs/hosting-options.md`; re-price on AWS's own pages first). New AWS
accounts may have credits; check the account's billing page. The budget alarm (`budget.tf`) notifies at 80% of the
month's limit and at a forecast of 100%. **It doesn't stop spending.**

Tear down:
```powershell
cd infrastructure\terraform\aws
terraform destroy -var environment=staging
```
- Production has deletion protection on the database and the load balancer: turn it off with a reviewed change
  first, never by hand.
- RDS takes a final snapshot (`<name>-final`). It costs storage until it's deleted:
  `aws rds delete-db-snapshot --db-snapshot-identifier loyalty-staging-final`.
- Secrets Manager entries wait 7 days (30 in production) before deletion and are billed meanwhile.
- The KMS key is scheduled for deletion (7 to 30 days), not deleted at once.
- Check afterwards, in the billing console, that nothing tagged `project=loyalty-support-modernization` remains.

## Render + Neon (the demo, option A, $0)
- Render: delete the service (Settings → Delete Web Service), then remove Render's GitHub access to the repository
  (GitHub → Settings → Applications).
- Neon: delete the project (Settings → Delete project). The free plan doesn't bill, but deleting removes the data.
- Then delete the demo's values from wherever they were pasted (Render's environment, `.env`).
