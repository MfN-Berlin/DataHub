FROM postgres:11.14-bullseye

# COPY ./files/postgres/init.sql /docker-entrypoint-initdb.d/
COPY ./files/postgres/db_init.sh /docker-entrypoint-initdb.d/
