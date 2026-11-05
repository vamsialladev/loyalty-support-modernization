-- Split the app's database role (ADR-0058): loyalty_owner owns the objects and runs migrations; loyalty_app runs the app.
-- Safe to run again, on a new database or on one left by an earlier milestone, where loyalty_app owns everything.
-- Run as a superuser, connected to the app's database, with: psql -v owner_pw=... -f app-owner.sql
\set ON_ERROR_STOP on

SELECT 'CREATE ROLE loyalty_owner LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'loyalty_owner') \gexec
ALTER ROLE loyalty_owner WITH LOGIN PASSWORD :'owner_pw';

REASSIGN OWNED BY loyalty_app TO loyalty_owner;
SELECT format('ALTER DATABASE %I OWNER TO loyalty_owner', current_database()) \gexec
ALTER SCHEMA public OWNER TO loyalty_owner;

GRANT USAGE ON SCHEMA public TO loyalty_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO loyalty_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO loyalty_app;
ALTER DEFAULT PRIVILEGES FOR ROLE loyalty_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO loyalty_app;
ALTER DEFAULT PRIVILEGES FOR ROLE loyalty_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO loyalty_app;

-- The grants above cover every table, so running this again must take these rights back (migration 0004 sets them first).
DO $$
DECLARE
  name text;
BEGIN
  FOREACH name IN ARRAY ARRAY['case_events', 'system_events'] LOOP
    IF to_regclass('public.' || name) IS NOT NULL THEN
      EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON %I FROM loyalty_app', name);
    END IF;
  END LOOP;
  IF to_regclass('public.alembic_version') IS NOT NULL THEN
    REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON alembic_version FROM loyalty_app;
  END IF;
END $$;
