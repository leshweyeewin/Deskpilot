# Deploy Deskpilot to Cloud Run

Prereqs: a GCP project with billing, `gcloud` authenticated, and the Gemini
model enabled (Vertex AI) or a Gemini API key.

```bash
export PROJECT=your-gcp-project-id
export REGION=asia-southeast1          # Singapore -- Cloud Run + Firestore
export MODEL_LOCATION=global           # Vertex only: newest Gemini lands here first
gcloud config set project $PROJECT
```

> **Region notes for SG:**
> - **Cloud Run + Firestore** run in `asia-southeast1` (Singapore) — low latency,
>   in-region data. **Firestore's location is permanent** for the project, so
>   choose it deliberately.
> - **Model location is separate.** With the **Gemini API key** path, region is
>   irrelevant (the API is global). With **Vertex AI**, the newest Gemini models
>   may not be in `asia-southeast1` yet — keep the model on `global` (or
>   `us-central1`) via `GOOGLE_CLOUD_LOCATION` while infra stays in Singapore.

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

> **PowerShell users — quote the env-vars value.** PowerShell treats an unquoted
> `A=1,B=2,C=3` as an array and hands gcloud a single space-joined string, so all
> your vars collapse into the first one (symptom: a `400 ... unexpected model name
> format` at runtime). Quote it:
> ```powershell
> gcloud run deploy deskpilot --source . --region asia-southeast1 --allow-unauthenticated `
>   --set-env-vars "DESKPILOT_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_CLOUD_PROJECT=$PROJECT" `
>   --set-secrets GOOGLE_API_KEY=gemini-api-key:latest
> ```
> To fix an already-deployed service without a full redeploy:
> ```powershell
> gcloud run services update deskpilot --region asia-southeast1 `
>   --update-env-vars "DESKPILOT_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=FALSE,GOOGLE_CLOUD_PROJECT=$PROJECT"
> ```

**Option B — Vertex AI (no API key; uses the runtime service account):**

```bash
gcloud run deploy deskpilot \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars DESKPILOT_MODEL=gemini-3.5-flash,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=$MODEL_LOCATION
```

The service itself runs in `asia-southeast1` (`--region $REGION`); only the Vertex
*model* call goes to `$MODEL_LOCATION`.

Grant the runtime service account `roles/datastore.user` (Firestore) and, for
Vertex, `roles/aiplatform.user`.

### Point it at your portfolio Google Sheet (optional)

Deskpilot reads positions from a **published Google Sheet** (CSV, no credentials).
Publish your sheet (File → Share → Publish to web → tab → CSV) and add the link as
an env var — no secret needed since the link is public read-only:

```bash
gcloud run services update deskpilot --region $REGION \
  --update-env-vars "DESKPILOT_PORTFOLIO_CSV_URL=https://docs.google.com/spreadsheets/d/e/XXXX/pub?gid=0&single=true&output=csv"
```

Columns are in `data/portfolio_template.csv`. If you skip this, the service uses
the shipped JSON sample. (PowerShell: quote the whole `--update-env-vars` value, as
noted above.)

### Deliver the plan to Telegram (optional)

To have each run push the finished plan to a Telegram chat, store the bot token as
a secret and set the chat id as an env var (both optional — unset means the step
is skipped and the run still succeeds):

```bash
printf '%s' "YOUR_TELEGRAM_BOT_TOKEN" | gcloud secrets create telegram-bot-token --data-file=-
gcloud run services update deskpilot --region $REGION \
  --update-secrets TELEGRAM_BOT_TOKEN=telegram-bot-token:latest \
  --update-env-vars TELEGRAM_CHAT_ID=123456789
```

Create the bot with @BotFather (token) and get your chat id from @userinfobot.

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
