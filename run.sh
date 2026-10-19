#!/usr/bin/env bash
# Dipanggil dari cron: muat .env, lalu jalankan Pricewatch dari folder project
set -euo pipefail
cd "$(dirname "$0")"
set -a
. ./.env
set +a
exec ./.venv/bin/python -m pricewatch.main "$@"
