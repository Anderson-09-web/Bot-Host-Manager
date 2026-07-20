#!/usr/bin/env bash
# Render build script — runs once before the service starts.
# Uses npx to run pnpm (no local/global install needed), builds the React
# frontend, then installs Python deps.
set -euo pipefail

echo ""
echo "══════════════════════════════════════════════════"
echo "  Discord Bot Hosting Panel — Render Build"
echo "══════════════════════════════════════════════════"
echo ""

# ── 1. Node dependencies via pnpm (run via npx, no install step) ──────────────
echo "→ Installing Node dependencies..."
npx --yes pnpm@10.26.1 install --no-frozen-lockfile

# ── 2. React frontend ─────────────────────────────────────────────────────────
echo "→ Building React frontend..."
BASE_PATH=/ PORT=3000 npx pnpm@10.26.1 --filter @workspace/discord-panel run build

echo "   Built to: artifacts/discord-panel/dist/public"

# ── 3. Python dependencies ────────────────────────────────────────────────────
echo "→ Installing Python dependencies..."
pip install --upgrade pip
pip install -r artifacts/api-server/requirements.txt

echo ""
echo "  Build complete."
echo ""
