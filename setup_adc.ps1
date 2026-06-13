$ErrorActionPreference = "Stop"

Write-Host "================================================================"
Write-Host "   Google Cloud Model API & Gemini: ADC setup script (Windows)"
Write-Host "================================================================"
Write-Host ""

# Check for gcloud
if (-not (Get-Command "gcloud" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Critical Error: gcloud CLI not found. Please install Google Cloud SDK." -ForegroundColor Red
    exit 1
}
Write-Host "✅ gcloud CLI detected." -ForegroundColor Green

# Ask for Project ID
Write-Host "--- Project Setup ---"
$PROJECT_ID = Read-Host "Enter your Google Cloud Project ID (NOT the name)"

if ([string]::IsNullOrWhiteSpace($PROJECT_ID)) {
    Write-Host "❌ Project ID cannot be empty." -ForegroundColor Red
    exit 1
}

# Authentication
Write-Host ""
Write-Host "--- Authenticating ---"
Write-Host "Authorizing Application Default Credentials (ADC). A browser window will open..."
gcloud auth application-default login

Write-Host ""
Write-Host "Setting active gcloud account..."
$ACCOUNT = (gcloud auth list --filter=status:ACTIVE --format="value(account)")
if ([string]::IsNullOrWhiteSpace($ACCOUNT)) {
    Write-Host "⚠️ Could not determine active account from ADC login. You might be prompted to login again." -ForegroundColor Yellow
    gcloud auth login --quiet
} else {
    gcloud config set account $ACCOUNT
    Write-Host "✅ Active account set to $ACCOUNT" -ForegroundColor Green
}

# Final Configuration
Write-Host ""
Write-Host "--- Finalizing Configuration ---"
gcloud config set project $PROJECT_ID
gcloud auth application-default set-quota-project $PROJECT_ID

Write-Host "🔌 Ensuring Google Cloud Model API is enabled..."
try {
    gcloud services enable aiplatform.googleapis.com
} catch {
    Write-Host "⚠️ Could not enable API (you might need an admin to do this). Proceeding..." -ForegroundColor Yellow
}

# Verification
Write-Host ""
Write-Host "--- Verifying Access ---"
$ACCESS_TOKEN = (gcloud auth print-access-token)

if ([string]::IsNullOrWhiteSpace($ACCESS_TOKEN)) {
    Write-Host "❌ Authentication failed. No token received." -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $ACCESS_TOKEN"
    "Content-Type"  = "application/json"
}
$body = '{ "contents": [{ "role": "user", "parts": [{ "text": "Reply ONLY with the word SUCCESS" }] }] }'
$uri = "https://aiplatform.googleapis.com/v1/projects/$PROJECT_ID/locations/global/publishers/google/models/gemini-2.5-flash:generateContent"

try {
    $response = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
    $responseText = $response.candidates[0].content.parts[0].text
    if ($responseText -match "SUCCESS") {
        Write-Host "🎉 SUCCESS! Your Model API access is fully working." -ForegroundColor Green
        $appData = [Environment]::GetFolderPath("ApplicationData")
        Write-Host "ADC Credentials stored at: $appData\gcloud\application_default_credentials.json"
    } else {
        Write-Host "⚠️ Authentication worked, but the API call returned: $responseText" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ Authentication worked, but the API call failed." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
}
