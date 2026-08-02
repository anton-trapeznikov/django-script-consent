#!/usr/bin/env bash
set -euo pipefail

# Локальный запуск всех проверок, аналогичных CI.
# Запускай из корня проекта:
#   ./scripts/check.sh
#
# Для автоисправления форматирования:
#   ./scripts/check.sh --fix
#
# Можно переопределить путь к виртуальному окружению:
#   VENV=.venv ./scripts/check.sh

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

echo "==> Python: $PYTHON"
$PYTHON --version

echo ""
echo "==> ruff check"
if $FIX_MODE; then
    ${BIN_DIR:+$BIN_DIR/}ruff check --fix .
else
    ${BIN_DIR:+$BIN_DIR/}ruff check .
fi

echo ""
echo "==> ruff format"
if $FIX_MODE; then
    ${BIN_DIR:+$BIN_DIR/}ruff format .
else
    ${BIN_DIR:+$BIN_DIR/}ruff format --check .
fi

echo ""
echo "==> black"
if $FIX_MODE; then
    ${BIN_DIR:+$BIN_DIR/}black .
else
    ${BIN_DIR:+$BIN_DIR/}black --check .
fi

echo ""
echo "==> isort"
if $FIX_MODE; then
    ${BIN_DIR:+$BIN_DIR/}isort .
else
    ${BIN_DIR:+$BIN_DIR/}isort --check-only .
fi

echo ""
echo "==> mypy"
${BIN_DIR:+$BIN_DIR/}mypy script_consent tests

echo ""
echo "==> Django tests"
DJANGO_SETTINGS_MODULE=tests.settings $PYTHON -m django test tests -v 2

echo ""
echo "==> JS tests"
npm run test:js

echo ""
echo "==> Все проверки пройдены"
