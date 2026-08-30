# Deploy Deskpilot to Cloud Run

Prereqs: a GCP project with billing, `gcloud` authenticated, and the Gemini
model enabled (Vertex AI) or a Gemini API key.

```bash
export PROJECT=your-gcp-project-id
export REGION=us-central1
gcloud config set project $PROJECT
```

## 1. Enable APIs

```bash
gcloud services enable run.googleapis.com firestore.googleapis.com \
    aiplatform.googleapis.com secretmanager.googleapis.com
```

## 2. Create the Firestore memory bank

```bash
gcloud firestore databases create --location=$REGION
```
The collection (`deskpilot_memory`) is created on first write — no schema step.

## 3. Store the Gemini API key (if not using Vertex)

```bash
printf '%s' "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=-
```
Skip this if you deploy with Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`), which
uses the service account instead.

## 4. Deploy

**Option A — Gemini API key:**

```bash
gcloud run deploy deskpilot \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars DESKPILOT_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_CLOUD_PROJECT=$PROJECT \
  --set-secrets GOOGLE_API_KEY=gemini-api-key:latest
```

**Option B — Vertex AI (no API key; uses the runtime service account):**

```bash
gcloud run deploy deskpilot \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars DESKPILOT_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=$REGION
```

Grant the runtime service account `roles/datastore.user` (Firestore) and, for
Vertex, `roles/aiplatform.user`.

## 5. Use it

- Dev UI: open the service URL + `/dev-ui/`, pick the `deskpilot` app, chat.
- REST: `POST {URL}/run` with an ADK run payload (see `/list-apps` and the ADK
  API docs).

## 6. (Optional) Daily autonomous run

Trigger the daily routine on a schedule with Cloud Scheduler hitting the `/run`
endpoint (or a small Cloud Run Job that calls `deskpilot.run`):

```bash
gcloud scheduler jobs create http deskpilot-daily \
  --schedule="0 6 * * 1-5" --time-zone="Asia/Singapore" \
  --uri="$(gcloud run services describe deskpilot --region $REGION --format='value(status.url)')/run" \
  --http-method=POST --message-body='{...ADK run payload...}'
```
