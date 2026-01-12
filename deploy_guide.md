# Deploying to Google Cloud Run with Cloud SQL

## Prerequisites
- Google Cloud SDK (`gcloud`) installed and authenticated.
- A Google Cloud Project.

## 1. Setup Cloud SQL (PostgreSQL)

**Enable the API (Done):**
```bash
gcloud services enable sqladmin.googleapis.com
```

**1. Create the Database Instance:**
*(This takes ~10-15 minutes)*
```bash
gcloud sql instances create cv-db-instance --database-version=POSTGRES_15 --tier=db-f1-micro --region=europe-west1 --root-password="YOUR_DB_ROOT_PASSWORD"
```

**2. Create the Database & User:**
```bash
gcloud sql databases create cv_tailor_db --instance=cv-db-instance
gcloud sql users create cv_user --instance=cv-db-instance --password="YOUR_SECURE_PASSWORD"
```

## 2. Deploy Application
Run this command from the project root. Be sure to replace `YOUR_SECURE_PASSWORD` with the one you set above.

```bash
gcloud run deploy cv-tailor-app \
  --source . \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --add-cloudsql-instances "cvglowup:europe-west1:cv-db-instance" \
  --set-env-vars "GEMINI_API_KEY=AIzaSyBfMh1QRB5aMlz9626g914d08f8MUh6D8U" \
  --set-env-vars "SECRET_KEY=generate_a_secure_random_key" \
  --set-env-vars "DB_USER=cv_user" \
  --set-env-vars "DB_PASS=YOUR_SECURE_PASSWORD" \
  --set-env-vars "DB_NAME=cv_tailor_db" \
  --set-env-vars "CLOUD_SQL_CONNECTION_NAME=cvglowup:europe-west1:cv-db-instance"
```
*Note: Make sure your Project ID is correct in the connection name (PROJECT_ID:REGION:INSTANCE_ID).*

## 3. Map Custom Domain (Optional)
```bash
gcloud beta run domain-mappings create --service cv-tailor-app --domain cvglowup.com --region europe-west1
```
