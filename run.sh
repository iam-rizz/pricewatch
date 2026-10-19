#!/usr/bin/env bash
# Wrapper untuk cron: load .env lalu jalankan monitor dari folder project
set -euo pipefail
cd "$(dirname "$0")"
set -a
. ./.env
set +a
exec ./.venv/bin/python -m pricewatch.main "$@"
