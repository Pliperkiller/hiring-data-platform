#!/usr/bin/env bash
# Build and (re)start the stack on the droplet.
# Reads a .env file alongside this script (not checked into the repo).
set -euo pipefail

cd "$(dirname "$0")"

docker compose up -d --build
