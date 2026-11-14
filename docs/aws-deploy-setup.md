# AWS deploy setup (for later; not done)

DEL-04, DEL-06; ADR-0084, ADR-0085. **Not done, and not to be done without the owner's approval and a budget:**
there's no AWS account for this project. This is what would make `.github/workflows/deploy.yml` work.

1. **Apply the Terraform** in a new account or a sandbox (`infrastructure/terraform/aws/`, after `docs/teardown.md`'s
   cost warnings). Fill the Secrets Manager entries it lists (`secrets_to_fill`).
2. **GitHub's OIDC provider in AWS:** an IAM identity provider for `token.actions.githubusercontent.com`, audience
   `sts.amazonaws.com`.
3. **A deploy role** that trusts only this repository's `production` environment
   (`repo:vamsialladev/loyalty-support-modernization:environment:production` in the trust policy's `sub` condition).
   Give it permission for ECR push, `ecs:UpdateService` and `ecs:RunTask` on this cluster, and `iam:PassRole` for the
   two task roles. Nothing else.
4. **Repository variables** (not secrets): `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`.
5. **The `production` environment** (repository Settings → Environments): required reviewers (the customer's change
   approver), and deployment branches limited to `main`.
6. **Then the workflow's last step** gets its real body: verify the image's provenance (`gh attestation verify`), push
   it to ECR, run the migrate task, update the services. Until then it stops by design.

No long-lived AWS key is ever created for CI; the role's credentials last an hour.
