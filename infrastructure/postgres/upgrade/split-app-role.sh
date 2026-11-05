#!/bin/sh
# Bring a volume from before Milestone 6 up to the split database role (ADR-0058). Safe to run again; `scripts\stack.ps1
# -Action up` runs it before anything connects. Reads the password from the container's environment, never from a file.
set -eu

if [ "${#APP_OWNER_DB_PASSWORD}" -lt 8 ]; then
  echo "split-app-role.sh: APP_OWNER_DB_PASSWORD is blank or shorter than 8 characters; nothing changed" >&2
  exit 1
fi
psql -v ON_ERROR_STOP=1 --quiet --username "$POSTGRES_USER" --dbname loyalty \
     -v owner_pw="$APP_OWNER_DB_PASSWORD" -f /pg-sql/app-owner.sql
