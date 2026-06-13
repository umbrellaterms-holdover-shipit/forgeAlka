#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -e '.[all]'
apex deps install ffmpeg pandoc --yes
apex deps doctor
if command -v npm >/dev/null 2>&1; then
  (cd apps/web && npm install)
else
  echo 'node/npm not found; skipping React dependency install' >&2
fi
python -m pytest -q
