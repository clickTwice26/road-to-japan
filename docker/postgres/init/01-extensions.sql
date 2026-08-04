-- Runs once, on first initialisation of an empty data volume.
-- Wipe the `postgres_data` volume to re-run it.

-- gen_random_uuid() is core since PG13; pgcrypto is here for digest/hmac.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Case-insensitive text, handy for emails and usernames.
CREATE EXTENSION IF NOT EXISTS citext;

-- Query performance stats, surfaced via pg_stat_statements.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

ALTER DATABASE roadtojapan SET timezone TO 'UTC';
