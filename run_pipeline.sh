#!/bin/bash
# Wrapper script for cron. Cron runs with a minimal environment, so we
# set the working directory and venv explicitly rather than relying on
# whatever PATH/cwd cron happens to have.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python3 etl.py
