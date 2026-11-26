#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export STREAMLIT_CONFIG_DIR="$(pwd)/.streamlit"
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
exec backend/.venv/bin/python -m streamlit run streamlit_app.py "$@"
