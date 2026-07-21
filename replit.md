# Discord Bot Hosting Panel

A professional self-hosted web panel for managing Python Discord bots — upload files, control the bot process, edit code in-browser, stream real-time logs, manage environment variables, and view system metrics. No terminal needed.

## Default Credentials

- **Username:** `admin`
- **Password:** `admin123`

Change this immediately in production via the Settings page or directly in the database.

## Run & Operate

- `pnpm --filter @workspace/discord-panel run dev` — React frontend (preview path `/`)
- `pnpm --filter @workspace/api-server run dev` — Python FastAPI backend (port 8080, path `/api`)
- `pnpm --filter @workspace/api-spec run codegen` — Regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm run typecheck` — Typecheck all packages

## Stack

- **Frontend:** React + Vite + TypeScript + TailwindCSS v4 + Wouter (routing)
- **Backend:** Python 3.11 + FastAPI + Uvicorn (with `--reload` in dev)
- **Database:** Neon PostgreSQL — async SQLAlchemy + asyncpg; env var: `NEON_DATABASE_URL`
- **File storage:** Cloudflare R2 (S3-compatible via boto3); env vars: `R2_*`
- **Auth:** JWT (PyJWT + bcrypt) — token stored in localStorage, injected via `setAuthTokenGetter`
- **API codegen:** Orval — generates React Query hooks from `lib/api-spec/openapi.yaml`

## Where Things Live

```
artifacts/api-server/          # Python FastAPI backend
  app/
    main.py                    # FastAPI app, CORS, routers, WebSockets, lifespan
    core/
      config.py                # Pydantic settings (reads all env vars)
      database.py              # Async SQLAlchemy engine, init_db(), seeding
      security.py              # hash_password, verify_password, JWT, get_current_user_id
    models/                    # SQLAlchemy ORM models (User, EnvVar, LogEntry, AuditLog, BotConfig)
    services/
      bot_manager.py           # Subprocess manager: start/stop/restart/kill, stdout streaming
      r2_storage.py            # Cloudflare R2 operations via boto3
      metrics_service.py       # psutil CPU/RAM/disk snapshot
    api/
      routes/                  # auth, bot, files, env_vars, metrics, logs, config, audit, health
      websockets/              # console.py (live logs), metrics.py (live stats)

artifacts/discord-panel/       # React frontend
  src/
    lib/auth.tsx               # AuthProvider, useAuth, setAuthTokenGetter wiring
    pages/                     # login, dashboard, files, console, env-vars, settings, not-found
    components/layout.tsx      # Persistent sidebar + top bar

lib/api-spec/openapi.yaml      # Source of truth for all API contracts
lib/api-client-react/          # Generated Orval hooks (do not edit manually)
```

## Architecture Decisions

- **NEON_DATABASE_URL** (not `DATABASE_URL`) to avoid conflict with Replit's managed Postgres key.
- **R2 for all file storage** — no permanent local disk. Bot files are synced from R2 to a temp work dir on each start.
- **python-jose was blocked** by Replit's package firewall — replaced with `PyJWT` + `bcrypt` directly (no passlib).
- **Upload/download endpoints excluded from OpenAPI spec** — multipart and binary responses cause Orval TS type collisions; those routes are called natively from the frontend with `fetch + FormData`.
- **WebSocket auth** via `?token=<jwt>` query param (not header, since browser WebSocket API doesn't support custom headers).
- **Bot work dir** is a temp directory that gets refreshed from R2 on every start — no persistent local bot files.

## Environment Variables Required

| Variable | Purpose |
|---|---|
| `NEON_DATABASE_URL` | Neon Postgres connection string |
| `R2_ACCOUNT_ID` | Cloudflare R2 account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `R2_BUCKET_NAME` | R2 bucket name |
| `R2_ENDPOINT_URL` | R2 S3-compatible endpoint |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens |
| `SESSION_SECRET` | Session secret (set by Replit) |
| `ENVIRONMENT` | `development` or `production` |
| `LOG_LEVEL` | `INFO`, `DEBUG`, `WARNING`, etc. |
| `CORS_ORIGINS` | Comma-separated allowed origins |

## Gotchas

- After adding/removing env vars in the panel, restart the bot for changes to take effect.
- `passlib` does NOT work with `bcrypt>=4.0.0` in Replit — use bcrypt directly (already done).
- The api-server dev script runs `bash start.sh` which calls `uvicorn` — not Node.js.
- To regenerate hooks after editing the OpenAPI spec: `pnpm --filter @workspace/api-spec run codegen`.

## Persistence Rules (mandatory)

- **`config_manager` is the only official method for persisting per-guild/per-server bot configurations.**
- Any cog, command, or system that needs to store settings or setup data per server MUST use `config_manager` (`cfg.get`, `cfg.set`, `cfg.delete`, `cfg.set_server`, `cfg.clear_server`).
- It is strictly forbidden to use JSON files, in-memory dicts/globals, SQLite, R2 direct writes, or any other storage method for per-guild data.
- This rule applies to all current and future additions to the project, without exception.
- `config_manager` persists all data to the PostgreSQL `bot_data` table via `/api/bot-data`. Data survives restarts and Render redeploys automatically.

## User Preferences

- Stack: Python FastAPI backend, React/Vite frontend, Neon PostgreSQL, Cloudflare R2.
- Dark mode only. No emojis anywhere in the UI.
- Mission Control / cockpit aesthetic — deep navy/slate + electric indigo/violet.
- Monospace fonts for all code, logs, and metrics.
