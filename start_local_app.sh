#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"
OUTPUT_DIR="${OUTPUT_DIR:-./eastmoney_reports}"
VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN=""

python_ok() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidate
  for candidate in python3.12 python3.11 python3.10 python3.9 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && python_ok "$candidate"; then
      PYTHON_BIN="$(command -v "$candidate")"
      return 0
    fi
  done
  return 1
}

if ! find_python; then
  echo "Python 3.9+ was not found."
  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    echo "Trying to install Python 3.12 with Homebrew..."
    brew install python@3.12 || brew install python
    find_python || {
      echo "Python may have been installed, but this terminal cannot find it yet."
      echo "Close this terminal and run ./start_local_app.sh again."
      exit 1
    }
  else
    echo "Please install Python 3.12, then run this script again:"
    echo "https://www.python.org/downloads/"
    exit 1
  fi
fi

echo "Using Python:"
"$PYTHON_BIN" --version

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Virtual environment Python was not found: $VENV_PYTHON"
  echo "Remove $VENV_DIR and run this script again."
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Installing or updating local app dependencies..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -e ".[app]"

echo "Importing existing outputs into local SQLite..."
"$VENV_PYTHON" -m eastmoney_report_scraper.cli import-existing --output-dir "$OUTPUT_DIR"

echo "Starting local app at http://$HOST:$PORT ..."
"$VENV_PYTHON" -m eastmoney_report_scraper.cli app --output-dir "$OUTPUT_DIR" --host "$HOST" --port "$PORT" --open-browser
