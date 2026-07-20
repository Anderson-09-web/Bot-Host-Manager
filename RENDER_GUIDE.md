# Deploying to Render

## Quick start (Blueprint — recommended)

1. Push this repo to GitHub (public or private).
2. Go to → **https://dashboard.render.com/blueprint/new**
3. Connect your GitHub repo and select the branch you want to deploy (`main`).
4. Render reads `render.yaml` and pre-fills everything.
5. Fill in the **secret env vars** when prompted (see table below).
6. Click **Apply** — done. Your URL will be `https://discord-bot-panel.onrender.com`.

---

## Service details

| Field | Value |
|---|---|
| **Service type** | Web Service |
| **Runtime** | Python 3 |
| **Branch** | `main` |
| **Build command** | `bash build.sh` |
| **Start command** | `cd artifacts/api-server && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --log-level info` |
| **Plan** | Free (spins down after 15 min inactivity) or Starter $7/mo (always on) |

---

## Environment variables

Set all of these in the Render dashboard under **Environment**.

### Required secrets (never commit these)

| Variable | Where to get it |
|---|---|
| `NEON_DATABASE_URL` | Neon console → your project → Connection string |
| `JWT_SECRET_KEY` | Generate: `openssl rand -hex 64` |
| `R2_ACCOUNT_ID` | Cloudflare dashboard → R2 → Account ID (top right) |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 → Manage API tokens → Create token |
| `R2_SECRET_ACCESS_KEY` | Same token creation page |
| `R2_BUCKET_NAME` | Your R2 bucket name |
| `R2_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |

### Optional (already set by render.yaml)

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | |
| `LOG_LEVEL` | `INFO` | Use `DEBUG` for troubleshooting |
| `STATIC_FILES_DIR` | `../discord-panel/dist/public` | Path to built frontend |
| `CORS_ORIGINS` | `*` | Lock to your Render URL in production |

---

## After deploy

1. Open your Render URL — you'll see the **Mission Control** login.
2. Log in with `admin` / your password.
3. Go to **Settings → Discord Connection**, paste your bot token and application ID.
4. Upload your bot files on the **Files** page (or they'll be pulled from R2).
5. Hit **Start** on the Dashboard.

---

## Free plan caveat

Render's free plan spins the service down after 15 minutes of inactivity.
The first request after spin-down takes ~30 seconds to wake up.
Upgrade to **Starter ($7/mo)** for always-on hosting.

---

## Updating

Push a new commit to `main` → Render auto-deploys.
No manual steps needed.
