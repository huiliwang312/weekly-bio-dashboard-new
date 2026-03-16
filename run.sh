#!/bin/bash
# run.sh — Launch the Streamlit dashboard
# Usage: ./run.sh

cd "$(dirname "$0")"
source .venv/bin/activate
streamlit run app.py
