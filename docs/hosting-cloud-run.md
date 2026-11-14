# The public demo on Google Cloud Run + Neon (the owner's choice, 2026-11-14)

Spec L1, PA-10; LIVE-01, LIVE-02; ADR-0088. Replaces Render (option A), which the owner dropped after hitting its
free-tier capacity limits before. **Instance-based billing, max 1, min 0, and no demo until the $10 stop is tested** (the owner, 2026-11-14). **Nothing is created until the owner says "go".** The owner does every click;
secrets go only into Google's and Neon's consoles, never into chat, a file or a commit.

Facts below come from the official pages, read 2026-11-14:
- Cloud Run pricing;
- the Cloud Run billing settings, container contract and health checks;
- `gcloud run deploy`;
- budgets, spend cap budgets, and disabling billing with notifications;
- Free Tier and Free Trial;
- Cloud Scheduler and Artifact Registry pricing;
- Neon's pricing, plans, scale-to-zero, regions and roles.

Anything a page didn't state is marked **not stated**. Costs are **projections from stated assumptions**, not
measurements, until the deploy runs.

## 1. Does a budget stop spending? Yes, for Cloud Run, with a spend cap
- **A normal budget only alerts.** Google: "Setting an *alerts-only* budget *doesn't* automatically cap Google Cloud
  … usage or spending."
- **A spend cap budget does stop it.** Cloud Run is one of the four services it covers today, alongside the Gemini
  API, Vertex AI and Cloud Run functions. When the cap is reached:
  - "all *new* usage for the specific service in the specified project is paused";
  - nothing is deleted;
  - it lifts automatically on the first day of the next month, or by hand ("Lift spend cap").
- **Three limits on the spend cap, stated plainly:**
  1. **It isn't instant:** "the enforcement of spend caps isn't instant and any cost overages are billed as normal."
     With at most one instance of 1 vCPU and 1 GiB, the most this service can add is about **$0.07 an hour** at list
     price (instance-based rates below). A delay of a few hours costs cents.
  2. **It counts gross, list-price costs:** "The estimated costs are calculated based on the list price of services
     and don't include savings and credits." The free tier is a discount, so a $10 cap pauses the demo when the
     *list-price* usage reaches $10. At that point the real bill is about **$4.78** (section 3). The cap is stricter
     than it looks, never looser.
  3. **It covers Cloud Run only.** Artifact Registry, Secret Manager, Logging and Scheduler aren't capped (section 4).
- **The "disable billing" function** (budget → Pub/Sub → a function that removes billing) **is not used.** Google warns
  it "removes Cloud Billing from your project, shutting down all resources. Resources might be irretrievably deleted",
  ends even the free-tier services, and "doesn't guarantee that you won't spend more than your budget". The spend cap
  is a real stop without deleting anything, for the only service whose cost grows with traffic. If you want a
  project-wide stop as well, this function is the only way, and I'd build it with Google's `SIMULATE_DEACTIVATION`
  test mode first.

**Your budgets:**
- **A $10 spend cap budget** on Cloud Run for this project. Add a 50% alert ($5 at list price) if the form offers
  alert thresholds; whether spend cap budgets take threshold rules is **not stated**.
- **A $5 alerts-only budget** on the whole project, with emails at 50%, 90% and 100% of actual costs. It catches
  anything outside Cloud Run.

## 2. Billing mode, and how the worker runs
The demo container runs three processes: the app, the worker and the mock customer API (`app/demo_launch.py`). The
worker polls the queue every second and runs investigations and write-path jobs in the background.

**Request-based billing** ("CPU is only allocated during request processing") would freeze the worker between
requests. Its job leases run on the wall clock (60 s), so a frozen worker would lose leases mid-job. To run on
request-based billing, the demo would need code it doesn't have:
1. **Jobs run inside requests:** while a case page polls (every 2 s, already in the templates), the request runs one
   due job before it renders.
2. **A Cloud Scheduler job** (one of the 3 free per billing account) calls a token-protected endpoint every 15 minutes
   for retries, sweeps and jobs nobody is watching. More often would keep Neon awake past its 100 CU-hours.
3. **What it would change:** an investigation advances only while someone has the page open, or every 15 minutes.
   The daily reset would also have to move into a request.

**Instance-based billing** ("CPU is allocated for the entire container instance lifecycle") runs the demo exactly as
built. Nothing changes in the code, and the worker behaves as it does everywhere else.
- **Scale to zero:** with minimum instances 0, "it won't be kept idle for longer than 15 minutes", so the instance
  stops after a quiet spell.
- **Cold start:** the next visitor starts a fresh one. The start runs the migrations and the daily reset when due, and
  the first page waits for it. The wait isn't measured yet; I'll measure it after the deploy and put it in the labels.

**Decision (owner, 2026-11-14): instance-based billing**, max 1 instance, min 0.
- **Why:** it stays inside the free tier at the expected traffic (section 3), and it keeps the demo honest: the system
  you see is the system that was built.
- **The gate:** the demo is deployed **only after the $10 stop is set up and tested** (5.2, 5.3).
- **If Google can't enforce a hard stop** (no "Spend cap enforcement" option, or the test cap never fires), stop
  before creating anything else, and the owner chooses request-based billing instead. That choice wouldn't change the
  stop itself: request-based billing relies on the same spend cap.

## 3. Cost projection (assumptions stated; not measured)
**Prices** (Cloud Run, us-central1 basis; the free tier is applied "using Tier 1 pricing", and `us-east5` is Tier 1):

| Billing | CPU, per vCPU-second | Memory, per GiB-second | Free each month (per billing account) |
|---|---|---|---|
| Instance-based | $0.000018 | $0.000002 | 240,000 vCPU-s, 450,000 GiB-s |
| Request-based | $0.000024 active | $0.0000025 active | 180,000 vCPU-s, 360,000 GiB-s, 2M requests |

**Assumption: one visit session bills about 1,200 s of instance time.** That is a start of up to 1 minute, about 5
minutes of use, and the instance staying alive up to 15 minutes afterwards. Visitors who overlap share the instance.

| Visit sessions a month | Instance time | List-price cost | Real bill (after the free tier) | What happens |
|---|---|---|---|---|
| up to about 200 | up to 240,000 vCPU-s | up to $4.80 | **$0** | free tier covers it |
| about 300 | 360,000 vCPU-s | $7.20 | about $2.16 | $5 alert-only budget not reached |
| about 416 | 500,000 vCPU-s | **$10.00** | about **$4.78** | **spend cap pauses Cloud Run** until the 1st |

These figures assume 1 vCPU and 1 GiB. Instance-based billing has no per-request charge. A portfolio demo is unlikely
to reach 200 sessions; a crawler hammering the URL is bounded by max 1 instance and the cap.

**Other services, kept at $0 by design:**

| Service | Free allowance (official) | This demo | Capped? |
|---|---|---|---|
| Artifact Registry | 0.5 GiB storage per billing account | one image of a few hundred MB; delete the old image after each deploy | no |
| Secret Manager | 6 active secret versions, 10,000 accesses a month | 2 secrets, read at each instance start | no |
| Cloud Logging | 50 GiB a month per project | JSON logs of a quiet demo | no |
| Cloud Build | 2,500 build-minutes a month | not used: you build the image on your own machine | — |
| Cloud Scheduler | 3 jobs per billing account | none (only the request-based design would use one) | — |
| Neon Free | 100 CU-hours a project, 1 GB storage, 5 GB egress; "no credit card required" | awake only while the instance lives | suspends compute if used up |

**Card and the Free Trial:**
- **Card:** a billing account is required even for the free tier, and the Free Trial asks for a card. Google
  describes it as a temporary authorization hold, not a charge.
- **During the trial:** "You will not be billed for any Google Cloud usage during your Free Trial."
- **After 90 days:** the trial account is closed and its "projects and resources will be stopped" unless you upgrade
  to a paid account. There's a 30-day grace period, then deletion. After you upgrade, the free tier continues and the
  budgets above apply.

## 4. What isn't capped, and the worst case
- **Cloud Run** has the hard stop; everything else in section 3's table can only alert.
- **Artifact Registry** costs $0.10 a GiB-month past 0.5 GiB. A forgotten extra image costs cents.
- **Outbound data:** Cloud Run includes 1 GiB a month free within North America. The demo's pages are small. Heavy
  traffic would show in the alert-only budget, and much of it would be stopped by the Cloud Run cap.
- **Neon** can't bill you: its Free plan suspends the database when its allowance is used up.

## 5. The owner's steps (placeholders only)
`PROJECT_ID` is the ID you choose. The region is `us-east5` (Columbus, Ohio, Tier 1), next to Neon's AWS
`us-east-2` (Ohio): every page makes several database round trips, so the two should be close. Commands are for
PowerShell.

### 5.1 Google account, project, billing
1. Go to console.cloud.google.com and sign in with your Google account. Start the **Free Trial**: you enter a card,
   and nothing is billed during the trial.
2. **Create a project:** name `loyalty-support-demo`. Note its **project ID** (`PROJECT_ID`). Check it's linked to the
   trial billing account (Billing → Account management).
3. Install the **Google Cloud CLI** for Windows from Google's site, then:
   ```powershell
   gcloud auth login
   gcloud config set project PROJECT_ID
   gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
   ```

### 5.2 Budgets, before anything runs
1. **Billing → Budgets & alerts → Create budget.**
   - Name: `loyalty-demo-cloud-run-cap`.
   - In **Define**, choose **Spend cap enforcement** (not "Alerts only"). An alerts-only budget can't be converted
     later, so pick spend cap here.
   - Choose project `PROJECT_ID` and service **Cloud Run**, then a Target amount of **$1** for the test in 5.3. It goes
     up to $10 after the test.
   - Add a 50% alert if offered, then **Finish**.
   - **If "Spend cap enforcement" isn't offered** (Google's pages don't say whether Free Trial accounts get it), stop
     here and tell me. Nothing else is created.
2. **Create budget** again.
   - Name: `loyalty-demo-alert-5`, **Alerts only**, scope the whole project, amount **$5**.
   - Thresholds: 50%, 90% and 100% of actual cost. Email billing admins (you).

### 5.3 Test the stop before the demo exists ($0 at list price under about $1)
The test uses Google's own sample container, so nothing of the demo exists yet. The image is
`us-docker.pkg.dev/cloudrun/container/hello`, from the Cloud Run quickstart. It runs at 4 vCPU and 2 GiB, so the $1 is
reached in hours, not days: 4 × $0.000018 + 2 × $0.000002 per second is about **$0.27 an hour** at list price. Three
and three-quarter hours is about 53,000 vCPU-seconds, inside the 240,000 free, so the real bill is $0.
1. Deploy the test service:
   ```powershell
   gcloud run deploy cap-test --image us-docker.pkg.dev/cloudrun/container/hello --region us-east5 --no-cpu-throttling --min-instances 0 --max-instances 1 --cpu 4 --memory 2Gi --allow-unauthenticated
   ```
2. Keep it alive with a request every 5 minutes, leaving the window open. Instance-based billing charges the
   instance's whole life, and an idle instance stops after 15 minutes:
   ```powershell
   $url = gcloud run services describe cap-test --region us-east5 --format "value(status.url)"
   while ($true) { $t = Get-Date -Format s; try { $c = (Invoke-WebRequest -UseBasicParsing $url).StatusCode } catch { $c = $_.Exception.Message }; "$t $c"; Start-Sleep 300 }
   ```
3. **Watch the cap:** Billing → Budgets & alerts. The spend cap budget's progress bar shows the list-price spend. Write
   down three times:
   - when it passes $1;
   - when its status turns **Enforced**;
   - when the loop's requests start failing. The response or error is **not documented**, so copy what the loop
     prints.
4. **If it isn't Enforced within 8 hours of passing $1, the stop doesn't work for us.** Press Ctrl+C, delete
   `cap-test` (step 6), and tell me before creating anything else. The choice then goes back to you.
5. **If it fired:** press Ctrl+C. Send me the three times and the loop's last lines.
6. Delete the test service: `gcloud run services delete cap-test --region us-east5`.
7. Raise the cap to $10 and lift it:
   - Edit the spend cap budget's target to **$10**, then press **Lift spend cap**. Google says services "might take up
     to one hour" to return to normal.
   - If the target can't be edited (not stated), delete the $1 budget and create a new spend cap budget at $10, as in
     5.2.1.
   - The test's roughly $1 of list-price spend counts this month, so this month leaves about $9 for the demo.
8. **Only now** go on to 5.4.

### 5.4 Neon: a new project
1. In console.neon.tech, click **New Project**.
   - Name: `loyalty-support-demo`. Postgres **16**. Region: **AWS US East 2 (Ohio)**.
   - Keep it **separate** from your hotel-ai and resort-concierge projects: the demo makes its own roles and
     databases inside its project.
2. In the branch's **compute settings** (the exact menu name isn't verified), set the size to **0.25 CU**, minimum
   and maximum. Free autoscales up to 2 CU, and a fixed small size keeps the 100 CU-hours lasting.
3. **Connect:** role `neondb_owner`, database `neondb`, **connection pooling off** (the direct string). It starts
   `postgresql://neondb_owner:` and ends `?sslmode=require`. Keep it for 5.5.1 only.

### 5.5 Secrets (values never shown)
1. In Google's console, go to **Security → Secret Manager → Create secret**.
   - Name `demo-database-url`.
   - Paste the Neon string as the value, then **Create**.
2. The app key: generate it and store it without displaying it. Run this from `cmd` so nothing adds a line break:
   ```powershell
   cmd /c "python -c ""import secrets; print(secrets.token_urlsafe(48), end='')"" | gcloud secrets create app-secret-key --data-file=-"
   ```
3. A service account that can read only these two secrets:
   ```powershell
   gcloud iam service-accounts create loyalty-demo-run --display-name="Loyalty demo on Cloud Run"
   gcloud secrets add-iam-policy-binding demo-database-url --member="serviceAccount:loyalty-demo-run@PROJECT_ID.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
   gcloud secrets add-iam-policy-binding app-secret-key --member="serviceAccount:loyalty-demo-run@PROJECT_ID.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
   ```

### 5.6 Build the image from `main` and push it (no Cloud Build)
```powershell
gcloud artifacts repositories create demo --repository-format=docker --location=us-east5
gcloud auth configure-docker us-east5-docker.pkg.dev
git clone --branch main https://github.com/vamsialladev/loyalty-support-modernization C:\projects\project1\lsm-release
cd C:\projects\project1\lsm-release
$sha = git rev-parse --short HEAD
docker build -f Dockerfile.demo -t "us-east5-docker.pkg.dev/PROJECT_ID/demo/loyalty-demo:$sha" .
docker push "us-east5-docker.pkg.dev/PROJECT_ID/demo/loyalty-demo:$sha"
```
The image is built from a fresh clone of `main` (PA-10: deploy only from `main`), and it's tagged with the commit.

### 5.7 Deploy (only after 5.3 passed)
```powershell
gcloud run deploy loyalty-demo `
  --image "us-east5-docker.pkg.dev/PROJECT_ID/demo/loyalty-demo:$sha" `
  --region us-east5 `
  --no-cpu-throttling `
  --min-instances 0 --max-instances 1 `
  --cpu 1 --memory 1Gi --concurrency 40 --timeout 300 --port 8080 `
  --allow-unauthenticated `
  --service-account "loyalty-demo-run@PROJECT_ID.iam.gserviceaccount.com" `
  --set-secrets "DEMO_DATABASE_URL=demo-database-url:latest,APP_SECRET_KEY=app-secret-key:latest" `
  --set-env-vars "PUBLIC_DEMO_MODE=true,AI_PROVIDER=mock,FEATURE_LIVE_AI=false,DEMO_MAX_CASES_PER_DAY=300,RATE_LIMIT_PER_MINUTE=120,APP_PROFILE=portfolio,LOG_LEVEL=INFO" `
  --startup-probe "httpGet.path=/healthz,httpGet.port=8080,periodSeconds=10,failureThreshold=30,timeoutSeconds=5"
```
- **`--no-cpu-throttling` is instance-based billing**, the owner's choice. `--min-instances 0 --max-instances 1` keep
  it to at most one instance, which stops after 15 idle minutes.
- **Money:** `AI_PROVIDER=mock` and `FEATURE_LIVE_AI=false` are set, and the code forces mock whenever
  `PUBLIC_DEMO_MODE` is on. No model API key exists anywhere in this project. **Never add one.**
- **The startup probe** allows 300 seconds (30 × 10 s, within the 600-second limit). That covers the first start's
  migrations and the world's load.

### 5.8 Verify, then tell me
1. Cloud Run → `loyalty-demo` → **Logs:** wait for `demo reset: removed 0 cases; mock world …`, then `Uvicorn running`.
2. Open the service URL. The banner says "Public demo: mock AI, synthetic data. Resets every day.", and the sign-in
   page shows two buttons and no password form. Click **Try it as an agent** and open a case.
3. If the logs show `permission denied to create role` or `…database`, the string isn't the owner's or pooling is on.
   Fix the secret (new version), then redeploy.
4. **Tell me only the `run.app` URL** (it isn't a secret). I'll then:
   - run `scripts/demo_smoke.py <URL>` and the Playwright happy path;
   - measure the cold start after 15+ quiet minutes;
   - record the results, and add the "(live)" link to the README with its labels.
5. After two days, read **Billing → Reports** and Cloud Run's billable instance time with me. That checks section 3's
   projection against reality.

### 5.9 Labels
- **The app's banner:** "Public demo: mock AI, synthetic data. Resets every day."
- **The README and any link:** "Live demo: mock AI, synthetic data. Free hosting: the first visit after a quiet spell
  takes about N seconds (N measured after deploy). Paused if the month's cap is reached."

### 5.10 Teardown
1. `gcloud run services delete loyalty-demo --region us-east5` (and `cap-test`, if it's still there)
2. `gcloud artifacts repositories delete demo --location us-east5`
3. `gcloud secrets delete demo-database-url` and `gcloud secrets delete app-secret-key`
4. Shut down the project (IAM & Admin → Settings → Shut down), then delete the Neon project.
