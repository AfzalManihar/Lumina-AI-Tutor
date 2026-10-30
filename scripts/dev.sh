#!/usr/bin/env bash
# Starts backend and frontend together (Ctrl+C stops both). MongoDB must already be running.
set -euo pipefail
here="$(dirname "$0")"
bash "$here/start-backend.sh" & BACK=$!
trap 'kill $BACK 2>/dev/null || true' EXIT INT TERM
bash "$here/start-frontend.sh"
