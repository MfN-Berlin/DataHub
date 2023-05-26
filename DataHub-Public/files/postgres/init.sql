-- \set PG_DBNAME 'echo "$POSTGRES_DATABASE"';
\set DB_USER `echo "$POSTGRES_USER"`;
\set DB_PASS `echo "$POSTGRES_PASSWORD"`;

CREATE USER DB_USER WITH PASSWORD 'DB_PASS';
CREATE DATABASE datahub ;
GRANT ALL ON DATABASE datahub TO DB_USER;