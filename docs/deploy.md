# Deploying CV Glowup to Google Cloud Run

No secrets belong in this file, in the repo, or in `--set-env-vars`. Everything
sensitive goes through **Secret Manager**.

## 0. Prerequisites

- `gcloud` CLI authenticated against your project (`gcloud auth login`).
- A Postgres database (Neon free tier works well — copy its connection string).
- A Gemini API key from https://aistudio.google.com/apikey (a fresh one — any
  key that ever appeared in git history is compromised and must be rotated).

```bash
export PROJECT_ID=your-project-id
export REGION=europe-west1
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 1. One-time: secrets

```bash
printf '%s' "$(openssl rand -base64 48)" | gcloud secrets create cvg-secret-key --data-file=-
printf '%s' "YOUR_NEW_GEMINI_KEY"        | gcloud secrets create cvg-gemini-key --data-file=-
printf '%s' "postgresql://user:pass@host/db?sslmode=require" \
  | gcloud secrets create cvg-database-url --data-file=-
```

## 2. Quickstart deploy (from your machine)

```bash
gcloud run deploy cvglowup \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 --concurrency 40 \
  --min-instances 0 --max-instances 4 \
  --set-env-vars "ENV=prod,ALLOWED_ORIGINS=https://cvglowup.com,https://www.cvglowup.com" \
  --set-secrets "SECRET_KEY=cvg-secret-key:latest,GEMINI_API_KEY=cvg-gemini-key:latest,DATABASE_URL=cvg-database-url:latest"
```

The container builds from the repo `Dockerfile` (frontend build + Typst binary,
~250 MB image). First request creates the database tables.

## 3. CI/CD via GitHub Actions (optional)

One-time setup:

```bash
gcloud artifacts repositories create cvglowup --repository-format=docker --location=$REGION

gcloud iam service-accounts create gh-deployer
for role in run.admin cloudbuild.builds.editor artifactregistry.writer iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member "serviceAccount:gh-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
    --role "roles/$role"
done
# Let Cloud Run read the secrets
for s in cvg-secret-key cvg-gemini-key cvg-database-url; do
  gcloud secrets add-iam-policy-binding $s \
    --member "serviceAccount:$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')-compute@developer.gserviceaccount.com" \
    --role roles/secretmanager.secretAccessor
done

gcloud iam service-accounts keys create gh-key.json \
  --iam-account gh-deployer@$PROJECT_ID.iam.gserviceaccount.com
```

In the GitHub repo settings:
- **Variable** `GCP_PROJECT_ID` = your project id.
- **Secret** `GCP_SA_KEY` = contents of `gh-key.json` (then delete the local file).

Now `.github/workflows/deploy.yml` deploys on manual dispatch or any `v*` tag.
(For a keyless setup, swap the auth step to Workload Identity Federation.)

## 4. Custom domain

```bash
gcloud beta run domain-mappings create --service cvglowup --domain cvglowup.com --region $REGION
```

Then add the DNS records it prints, and keep `ALLOWED_ORIGINS` in sync.

## 5. Optional features

| Feature | Enable by |
|---|---|
| Paid plans (Stripe) | secrets `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, env `STRIPE_PRICE_PLUS`, `STRIPE_PRICE_PRO`, `PUBLIC_BASE_URL`; point a Stripe webhook at `/api/billing/webhook` |
| Google sign-in | env `GOOGLE_CLIENT_ID` (OAuth client of type Web, authorized origin = your domain) |
| Ads for free tier | env `ADSENSE_CLIENT` after AdSense approval |

## 6. Migrating legacy accounts

The new schema lives in new tables (`users`, …) and does not collide with the
legacy Flask tables (`user`, `application`). Old password hashes verify as-is
(werkzeug pbkdf2 format). To copy legacy accounts:

```sql
INSERT INTO users (email, password_hash, plan, language)
SELECT email, password_hash, 'free', 'en' FROM "user"
ON CONFLICT (email) DO NOTHING;
```

Legacy `cv_text` can be re-imported by users via Settings → Master CVs.

## Operations notes

- Logs: `gcloud run services logs read cvglowup --region $REGION` (structured logging to stdout).
- The app is stateless: job state and documents live in Postgres, so
  autoscaling and restarts are safe. Generated PDFs are stored per-document
  and regenerated on demand.
- Typst compiles are capped by `COMPILE_CONCURRENCY` (default 4 per instance);
  generation jobs by `JOB_CONCURRENCY` (default 6 per instance).
