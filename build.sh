#!/usr/bin/env bash
# Render build script — runs once before the service starts.
# Installs pnpm locally (no global/system write needed), builds the React
# frontend, then installs Python deps.
set -euo pipefail

echo ""
echo "══════════════════════════════════════════════════"
echo "  Discord Bot Hosting Panel — Render Build"
echo "══════════════════════════════════════════════════"
echo ""

# ── 1. pnpm (local install — avoids read-only /usr/bin on Render) ─────────────
echo "→ Installing pnpm locally..."
npm install --no-save pnpm
export PATH="$PWD/node_modules/.bin:$PATH"

echo "→ Installing Node dependencies..."
pnpm install --frozen-lockfile

# ── 2. React frontend ─────────────────────────────────────────────────────────
echo "→ Building React frontend..."
BASE_PATH=/ PORT=3000 pnpm --filter @workspace/discord-panel run build

echo "   Built to: artifacts/discord-panel/dist/public"

# ── 3. Python dependencies ────────────────────────────────────────────────────
echo "→ Installing Python dependencies..."
pip install --upgrade pip
pip install -r artifacts/api-server/requirements.txt

echo ""
echo "  Build complete."
echo ""
