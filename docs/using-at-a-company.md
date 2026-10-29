# Using this foundation at a company

> Documentation only (PURP-11). This project is an independent portfolio simulation with synthetic data. Nothing in
> it is approved for any company's data or systems.

Before any part of it touches company data or systems:

1. **Check your employer's policies first:** intellectual-property assignment, personal-project and open-source
   contribution rules. Bringing personal code into a company, or company work into a personal repo, may need written
   approval.
2. **Security and privacy approval:** the company's security team reviews the threat model, and its privacy or legal
   team decides what data may be processed, where, and for how long. Use the templates in `docs/governance.md`.
3. **Use the approved-deployment profile:** `APP_PROFILE=approved`, enterprise identity (the company's IdP), managed
   secrets, explicit model and telemetry destinations, and `python -m app.preflight --profile approved` showing READY.
4. **Write real-system adapters:** replace each stand-in as described in `docs/real-system-swap-guide.md`, with the
   system owner's approval and least-privilege access.
5. **Approve the model provider:** vendor management confirms contract terms, retention and region before any company
   data reaches a model.
6. **Run the evaluation on company-representative cases** (authorized, minimised) before any pilot, and follow the
   rollout gates in `docs/business-requirements.md` §7.
7. **Never** connect personal browser sessions, personal accounts or personal API keys to company systems.
