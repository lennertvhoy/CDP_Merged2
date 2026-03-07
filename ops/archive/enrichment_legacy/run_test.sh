#!/bin/bash
export TRACARDI_API_URL="http://52.148.232.140:8686"
export TRACARDI_USERNAME="admin@cdpmerged.local"
export TRACARDI_PASSWORD="admin"
export TRACARDI_SOURCE_ID="kbo-source"

poetry run python run_phase1.py
