#!/usr/bin/env bash
# Backward-compatible entrypoint — prefer ./check.sh from the repo root.
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/check.sh" "$@"
