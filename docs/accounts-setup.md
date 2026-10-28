# Accounts and keys setup (Appendix K)

**Status:** Documentation-only, first version (Milestone 1). Each section is re-verified against the vendor's current
official docs when its milestone is reached, and the check date is added to the section. Free-tier limits and menu
paths marked *unverified* have not been checked yet; don't rely on them for spending decisions.

## Rules (read first)
- Put values **only** in `.env` (Git-ignored) or a secret manager. **Never paste a key into chat.**
- Use scoped API tokens, never account passwords. AWS uses SSO profiles, never long-lived access keys.
- Set a spending limit in each provider's console as well as the app's budget variables.
- An empty variable is fine: that feature runs in mock/offline mode or its exercise shows "Blocked: needs `<VAR>`".
- After filling `.env`, check readiness without revealing values:

```powershell
uv run python -m app.preflight --profile portfolio
```

```powershell
uv run python -m app.preflight --profile live-model
```

The output says `set`, `missing` or `invalid format` per variable, and which features are unlocked. It never prints
a value.

## Core (no account needed)

| Variable | How to fill it |
|---|---|
| `APP_SECRET_KEY` | Run `uv run python -c "import secrets;print(secrets.token_urlsafe(48))"` and paste the output into `.env` yourself |
| `POSTGRES_PASSWORD`, `MOCK_API_TOKEN` | Any local development value (at least 12 characters). Local Docker only |
| `KEYCLOAK_ADMIN_PASSWORD`, `OIDC_CLIENT_SECRET` | Local values; the Keycloak setup script (Milestone 9) generates the client secret |

## Anthropic Claude API (runtime model; Milestone 8)
- **Sign-up:** https://console.anthropic.com (official console).
- **Key:** Console → API keys → create a key in a workspace used only for this project. Fills `ANTHROPIC_API_KEY`.
- **Model:** `ANTHROPIC_MODEL` takes an exact model ID from Anthropic's current models page. Planned default:
  Claude Haiku 5.5 (ADR-0006); re-verified in Milestone 8.
- **Spending limit:** set a monthly limit for the workspace in the console (*menu path unverified*), and keep
  `LLM_BUDGET_USD_PER_RUN` / `LLM_BUDGET_USD_TOTAL` in `.env`. The spec suggests $5 for the first live run.
- **Revoke:** Console → API keys → disable or delete the key. After rotating, run the live smoke test with the old
  key to prove it fails (addendum item 9).
- **Free tier:** *unverified*.

## Amazon Bedrock (enterprise endpoint; Milestone 12, configure only)
- `aws configure sso` creates a named profile; put its name in `AWS_PROFILE` and the region in `AWS_REGION`.
  No access keys in `.env`.
- Model access is requested in the Bedrock console per region; `BEDROCK_MODEL_ID` *(verify)* comes from the current
  Bedrock model list.
- **Spending limit:** AWS Budgets alert on the account. **Revoke:** remove the SSO permission set or sign out
  (`aws sso logout`).

## Kimi, GLM, Qwen (one at a time; Milestone 15)
Variables `MOONSHOT_API_KEY`, `ZAI_API_KEY`, `DASHSCOPE_API_KEY` are all *(verify)*: names, sign-up pages, regions and
licences are checked against each vendor's official docs before any use. A local OpenAI-compatible server
(`LOCAL_MODEL_BASE_URL`) needs no account. Data goes to one of them only by explicit selection.

## GitHub (Milestone 1 onward, with the owner's OK to create the repo)
- **Token** (only if a script needs one; `gh auth` already covers normal use): github.com → Settings → Developer
  settings → Personal access tokens → Fine-grained tokens → Repository access: **only this repository**, minimum
  permissions. Fills `GH_TOKEN`. Set an expiry date.
- **Revoke:** the same page → Delete.
- CodeRabbit needs no key: install its GitHub app on this single repository from its official site (Milestone 15).

## Supabase (Milestone 15)
- **Sign-up:** https://supabase.com/dashboard.
- **Keys:** Project Settings → API keys. `SUPABASE_PUBLISHABLE_KEY` is browser-safe; `SUPABASE_SECRET_KEY` is
  server-only and never goes into frontend code or `NEXT_PUBLIC_*` / `VITE_*` variables. `SUPABASE_DB_URL` is the
  Postgres connection string. Key names follow Supabase's publishable/secret key model *(re-verify)*.
- **Free tier and spend cap:** *unverified*. **Revoke:** rotate or delete the secret key in the same settings page.

## Vercel (only after bolt.new and the owner's OK)
- Account → Settings → Tokens → create a token scoped to one team/project *(verify)*. Fills `VERCEL_TOKEN`;
  `VERCEL_PROJECT_ID` and `VERCEL_ORG_ID` come from the linked project.
- **Revoke:** delete the token. **Free tier:** *unverified*.

## Monday.com and Miro (Milestone 15, optional)
- `MONDAY_API_TOKEN` *(verify)*: personal API token from the Monday developer section. `MONDAY_BOARD_ID`: the board's
  number from its URL.
- `MIRO_ACCESS_TOKEN` *(verify)*: from a Miro developer app with board scopes only. `MIRO_BOARD_ID`: from the board URL.
- **Revoke:** regenerate or delete the token in each product. No invites or messages are sent by this project.

## Telegram (only if the owner chooses the generic exercise instead of Mira)
- Create a bot with @BotFather; it gives `TELEGRAM_BOT_TOKEN`. `TELEGRAM_CHAT_ID` is the owner's own chat.
- **Revoke:** @BotFather → `/revoke`. Synthetic project information only.

## Browser-login tools (no keys)
bolt.new, Cursor, Egolite, Invoco, Mira and the first CodeRabbit / Miro / Monday setup need a one-time manual login
by the owner. Exact steps are given when each exercise starts. This project never uses the owner's browser sessions
or saved passwords.

## Hosting dashboards (addendum item 10)
When a hosted deployment is approved, the owner gets the secrets block as valid TOML with every value quoted (names
only, values left for the owner to paste into the dashboard) plus the check that proves the app received them: the
startup log line and the preflight output showing `set` / `missing` per variable.
