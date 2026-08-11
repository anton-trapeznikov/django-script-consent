#!/usr/bin/env bash
set -euo pipefail

# Локальный запуск всех проверок, аналогичных CI.
# Из корня репозитория:
#   ./check.sh
#   ./check.sh --fix
#
# Переопределение venv / python:
#   VENV=.venv ./check.sh
#   PYTHON=python3.12 ./check.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FIX_MODE=false
if [[ "${1:-}" == "--fix" ]]; then
    FIX_MODE=true
fi

VENV="${VENV:-.venv}"
if [[ -d "$VENV" ]]; then
    PYTHON="${PYTHON:-$VENV/bin/python}"
    BIN_DIR="$VENV/bin"
else
    PYTHON="${PYTHON:-python3}"
    BIN_DIR=""
fi

run_tool() {
    local name="$1"
    shift
    if [[ -n "$BIN_DIR" && -x "$BIN_DIR/$name" ]]; then
        "$BIN_DIR/$name" "$@"
    else
        "$name" "$@"
    fi
}

echo "==> Python: $PYTHON"
$PYTHON --version

echo ""
echo "==> ruff check"
if $FIX_MODE; then
    run_tool ruff check --fix .
else
    run_tool ruff check .
fi

echo ""
echo "==> ruff format"
if $FIX_MODE; then
    run_tool ruff format .
else
    run_tool ruff format --check .
fi

echo ""
echo "==> black"
if $FIX_MODE; then
    run_tool black .
else
    run_tool black --check .
fi

echo ""
echo "==> isort"
if $FIX_MODE; then
    run_tool isort .
else
    run_tool isort --check-only .
fi

echo ""
echo "==> mypy"
run_tool mypy script_consent tests

echo ""
echo "==> Django tests"
DJANGO_SETTINGS_MODULE=tests.settings $PYTHON -m django test tests -v 2

echo ""
echo "==> JS tests"
npm run test:js

echo ""
echo "==> Все проверки пройдены"
