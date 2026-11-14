# Shared responsibility

Spec F.2; DEL-07; ADR-0086. Who answers for what when the system runs on someone else's platform. The providers'
own shared-responsibility pages are the authority; this page names this system's side. No provider here holds real
data: everything is synthetic, and the only hosting chosen is the demo (Render + Neon, option A).

| Platform | The provider runs | This system (the team running it) is responsible for |
|---|---|---|
| **AWS** (reference path, never applied) | Physical security, the hypervisor, the managed services' own availability (Fargate, RDS, ALB, KMS, Secrets Manager) | The network design and security groups; IAM roles and their scope; encryption settings and key policy; filling and rotating secrets; patching the images; database backups' retention and restore drills; the budget alarm and teardown; logging what's needed and no more |
| **Render** (the demo) | The machines, TLS at its edge, builds and restarts | The image and its dependencies; environment values pasted into the dashboard; the demo's reset job; keeping it labelled "mock AI, synthetic data"; access to the GitHub repository limited to this one |
| **Neon** (the demo's Postgres) | The database service, storage, its own point-in-time history | Roles and grants (`infrastructure/postgres/sql/`); what's stored (synthetic only); the connection string kept out of code |
| **Supabase** (named in the spec as an option; not used) | The managed Postgres, auth and storage services | The same as Neon, plus row-level security if its auth were used; not chosen: the owner picked option A, Render + Neon (`docs/hosting-options.md`) |
| **Vercel** (named in the spec as an option; not used) | The edge network and builds | Not used: the app needs a long-running worker, which Vercel doesn't host |
| **Model providers** (Anthropic API; Claude via Amazon Bedrock, configured only) | Model availability, the API's security, their data handling under their terms | What is sent (only what the case needs, redacted first; `app/ai/redaction.py`); the allowed-model list and retirement tracking; spending caps; never sending a secret; checking the provider's terms (`docs/enterprise-integration.md`, provider checklist) |
| **GitHub** | The platform, Actions runners, secret scanning | Workflow permissions, pinned actions, what runs on pull requests from forks, branch and environment protection |

**Common to every platform:** the application's own authorization, approval and audit trail are always this
system's. No platform's controls replace the supervisor's approval of every adjustment.
