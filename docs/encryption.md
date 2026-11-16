# Encryption in transit and at rest (SEC-15)

What this repository sets and has checked, kept apart from what a hosting provider manages. Nothing in the "managed"
column is verified by us: it is the provider's job, and it gets checked on the provider's own pages before a real
deployment (`docs/shared-responsibility.md`).

| Where | In transit | At rest | Who sets it | Checked how |
|---|---|---|---|---|
| **Local Compose** (`docker compose up`) | None. Browser to app is plain HTTP on `127.0.0.1` only; app, worker, mock API and Postgres talk over Docker's private network without TLS. Cookies are not marked `Secure`, because the browser would not send them back over HTTP | None added. Postgres data sits in a Docker volume on the laptop's disk; any protection is the laptop's own disk encryption, which this repository doesn't check | This repository | `app/settings.py` `cookie_secure` (off only for local profiles); ports bound to `127.0.0.1` in `docker-compose.yml` |
| **Public demo** (Cloud Run + Neon, ADR-0088; not deployed yet) | Browser to Cloud Run: HTTPS on the `run.app` address, ended at Google's front end (managed). The two secrets come from Secret Manager (`--set-secrets`). Cloud Run to Neon: the connection string carries `sslmode=require`, and the launcher keeps it on every role's connection string. Inside the container, app to mock API is HTTP on `127.0.0.1` | Neon's storage (managed) | Google (Cloud Run, Secret Manager) and Neon for the edges, secrets and storage; this repository for `sslmode` and `Secure` cookies | `tests/test_demo_launch.py` (the query string survives in `url_for`); `PUBLIC_DEMO_MODE` turns `Secure` cookies on (`tests/test_demo_mode.py` uses an HTTPS test client). Cloud Run's TLS and Neon's storage encryption: provider-managed, to be read on their pages at deploy |
| **AWS reference path** (Terraform, validate only, never applied) | Internet to ALB: HTTPS, listener policy `ELBSecurityPolicy-TLS13-1-2-2021-06` with an ACM certificate. ALB to the tasks: HTTP inside the VPC's private subnets. Tasks to RDS: TLS required by the parameter `rds.force_ssl = 1` (a connection without TLS is refused) | One KMS key of this deployment's own, with yearly rotation, for RDS storage, the RDS master-password secret, Performance Insights, the app secrets, the CloudWatch log groups and the alerts topic. The ALB-logs bucket uses S3-managed keys (`AES256`), not the KMS key | This repository (Terraform); AWS runs the key service | `scripts\terraform_check.ps1` (`fmt`, `validate`, Trivy config scan, 0 fixable findings); `infrastructure/terraform/aws/rds.tf`, `alb.tf`, `secrets.tf`, `observability.tf` |

## Gaps, stated
- **ALB to tasks is plain HTTP** inside private subnets. A customer with an in-VPC encryption rule would add TLS on the
  target group and in the app container.
- **The AWS settings are validated, not applied.** `terraform validate` and Trivy check the configuration; no RDS
  instance has been created to prove `rds.force_ssl` refuses a plain connection.
- **Local data isn't encrypted by us.** Only synthetic data is ever used locally.
- **The demo's provider settings are unverified** until the owner deploys; the smoke test checks HTTPS works, not how
  the provider stores data.
