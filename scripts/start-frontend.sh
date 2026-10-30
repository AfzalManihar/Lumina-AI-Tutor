#!/usr/bin/env bash
# Installs frontend dependencies and starts Vite on http://localhost:5173 (proxies /api to the backend)
set -euo pipefail
cd "$(dirname "$0")/../frontend"
[ -d node_modules ] || npm install
exec npm run dev
