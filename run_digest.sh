#!/bin/bash
# run_digest.sh — wrapper for launchd/cron weekly digest job
# Activates venv, loads env vars, runs send_digest.py
#
# SETUP: Update PROJECT_DIR below to match where you cloned this project.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOGFILE="${PROJECT_DIR}/digest.log"
ENV_FILE="${PROJECT_DIR}/.env.digest"

# Append all output to log
exec >> "${LOGFILE}" 2>&1

echo "=========================================="
echo "Digest run started: $(date)"
echo "=========================================="

cd "${PROJECT_DIR}"

# Load environment variables
if [ -f "${ENV_FILE}" ]; then
    set -a
    source "${ENV_FILE}"
    set +a
else
    echo "ERROR: ${ENV_FILE} not found"
    echo "Create .env.digest with SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_TO"
    exit 1
fi

# Activate venv and run
source .venv/bin/activate
python send_digest.py

echo "Digest run completed: $(date)"
echo ""
