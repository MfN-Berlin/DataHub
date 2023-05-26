#!/bin/bash
set -e
export PGPASSWORD=$POSTGRES_PASSWORD;
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DATABASE" <<-EOSQL
  CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
  CREATE DATABASE $DB_NAME;
  CREATE DATABASE $AIRFLOW_DB_NAME;
  GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
  GRANT ALL PRIVILEGES ON DATABASE $AIRFLOW_DB_NAME TO $DB_USER;
EOSQL