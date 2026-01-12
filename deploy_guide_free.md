# Deploying to Google Cloud Run (Free Database Option)

## Option: Use Supabase (Free PostgreSQL)

Since Cloud SQL costs money (~$10-20/mo minimum), a great alternative for personal projects is **Supabase**. They offer a generous free tier for PostgreSQL databases.

### 1. Get a Database URL
1.  Go to [Supabase.com](https://supabase.com) and create a free account.
2.  Create a "New Project". giving it a Name (e.g., `CV Tailor`) and a strong Database Password (SAVE THIS!).
3.  Once created, go to **Project Settings** -> **Database**.
4.  Copy the **Connection String** (URI).
    *   It should look like: `postgresql://postgres:[YOUR-PASSWORD]@db.xyz.supabase.co:5432/postgres`
    *   **Important**: Make sure to replace `[YOUR-PASSWORD]` with the real password you just set.

### 2. Deploy with the URL
Run this command. Replace `YOUR_SUPABASE_CONNECTION_STRING` with the value you copied.

```bash
gcloud run deploy cv-tailor-app \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=AIzaSyBfMh1QRB5aMlz9626g914d08f8MUh6D8U" \
  --set-env-vars "SECRET_KEY=generate_a_secure_random_key" \
  --set-env-vars "DATABASE_URL=YOUR_SUPABASE_CONNECTION_STRING"
```

*Note: You do NOT need the `--add-cloudsql-instances` or the other `DB_` variables anymore.*

## Option: Use Neon (Free Serverless Postgres)
Similar to Supabase, [Neon.tech](https://neon.tech) offers a free Postgres tier.
1. Create a project on Neon.
2. Copy the connection string.
3. Use the same deploy command above with the Neon URL.
