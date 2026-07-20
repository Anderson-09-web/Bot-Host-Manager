#!/usr/bin/env bash
# Render build script — runs once before the service starts.
# Installs pnpm, builds the React frontend, then installs Python deps.
set -euo pipefail

echo ""
echo "══════════════════════════════════════════════════"
echo "  Discord Bot Hosting Panel — Render Build"
echo "══════════════════════════════════════════════════"
echo ""

# ── 1. Node / pnpm ────────────────────────────────────────────────────────────
echo "→ Enabling pnpm via corepack..."
corepack enable
corepack prepare pnpm@latest --activate

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
