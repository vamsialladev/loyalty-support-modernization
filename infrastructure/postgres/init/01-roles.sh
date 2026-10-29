#!/bin/sh
# One Postgres server, separate roles and databases (ADR-0036). Runs once, on an empty data volume.
# loyalty_app owns the app database; mock_api owns the mock customer API database (and its test database).
# Neither role can connect to the other's database. Passwords come from the environment, never from this file.
set -eu

# A blank password must never create a role: refuse before anything is created (verification log, M4 env fix).
for name in APP_DB_PASSWORD MOCK_API_DB_PASSWORD; do
  eval "value=\${$name:-}"
  if [ "${#value}" -lt 8 ]; then
    echo "01-roles.sh: $name is blank or shorter than 8 characters; no roles created" >&2
    exit 1
  fi
done

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_pw="$APP_DB_PASSWORD" -v mock_pw="$MOCK_API_DB_PASSWORD" <<'EOSQL'
CREATE ROLE loyalty_app LOGIN PASSWORD :'app_pw';
CREATE ROLE mock_api LOGIN PASSWORD :'mock_pw';
ALTER DATABASE loyalty OWNER TO loyalty_app;
ALTER SCHEMA public OWNER TO loyalty_app;
CREATE DATABASE mock_customer_api OWNER mock_api;
CREATE DATABASE mock_customer_api_test OWNER mock_api;
REVOKE CONNECT ON DATABASE loyalty FROM PUBLIC;
REVOKE CONNECT ON DATABASE mock_customer_api FROM PUBLIC;
REVOKE CONNECT ON DATABASE mock_customer_api_test FROM PUBLIC;
GRANT CONNECT ON DATABASE loyalty TO loyalty_app;
GRANT CONNECT ON DATABASE mock_customer_api TO mock_api;
GRANT CONNECT ON DATABASE mock_customer_api_test TO mock_api;
EOSQL

for db in mock_customer_api mock_customer_api_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" -c "ALTER SCHEMA public OWNER TO mock_api;"
done
