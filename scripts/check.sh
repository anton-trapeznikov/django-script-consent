#!/usr/bin/env bash
# Backward-compatible entrypoint — prefer ./check.sh from the repo root.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/check.sh" "$@"
