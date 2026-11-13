#!/bin/sh
# The real-Postgres job's database setup, shared by CI (.github/workflows/ci.yml) and scripts/ci_local.ps1, so the two
# can't drift (Milestone 12, DEL-02). POSIX sh: it also runs inside the postgres:16 alpine image.
# Needs: psql, a Postgres whose superuser is mock_api with database mock_customer_api_test, and
#   PGHOST_PORT  host:port of that Postgres (default 127.0.0.1:5432)
#   CI_DB_PASSWORD  the throwaway password for every role (default ci-only-throwaway)
#   SQL_DIR  folder holding app-owner.sql (default infrastructure/postgres/sql)
set -eu
HOSTPORT="${PGHOST_PORT:-127.0.0.1:5432}"
PW="${CI_DB_PASSWORD:-ci-only-throwaway}"
SQL_DIR="${SQL_DIR:-infrastructure/postgres/sql}"
SUPER="postgresql://mock_api:${PW}@${HOSTPORT}"

# A Milestone 5 database, where loyalty_app is the owner; the role split must keep its login (ADR-0058).
psql "$SUPER/mock_customer_api_test" -c "CREATE ROLE loyalty_app LOGIN PASSWORD '${PW}'" \
  -c "CREATE DATABASE loyalty_m5 OWNER loyalty_app"
psql "$SUPER/loyalty_m5" -c "REVOKE CONNECT ON DATABASE loyalty_m5 FROM PUBLIC" \
  -c "GRANT CONNECT ON DATABASE loyalty_m5 TO loyalty_app"
BEFORE=$(psql "$SUPER/loyalty_m5" -tAc "select datacl from pg_database where datname = 'loyalty_m5'")
test "$BEFORE" = "{=T/loyalty_app,loyalty_app=CTc/loyalty_app}" || { echo "not the Milestone 5 state: $BEFORE"; exit 1; }
psql "$SUPER/loyalty_m5" -v owner_pw="$PW" -f "$SQL_DIR/app-owner.sql"
test "$(psql "postgresql://loyalty_app:${PW}@${HOSTPORT}/loyalty_m5" -tAc "select current_user")" = loyalty_app
test "$(psql "$SUPER/loyalty_m5" -tAc "select pg_get_userbyid(datdba) from pg_database where datname = 'loyalty_m5'")" = loyalty_owner

# The app's throwaway database and its two roles, from the same script the stack uses.
psql "$SUPER/mock_customer_api_test" -c "CREATE DATABASE loyalty_test"
psql "$SUPER/loyalty_test" -v owner_pw="$PW" -f "$SQL_DIR/app-owner.sql"
echo "postgres setup done"
