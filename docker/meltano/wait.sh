#!/bin/sh

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME; do sleep 1; done
while ! PGPASSWORD=$PG_PASSWORD psql -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME $PG_DATABASE -c "select * from meltano.alembic_version"; do sleep 1; done

meltano "$@"