#!/bin/bash

python scripts/generate_meltano_config.py

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_HOST -p $PG_PORT -U $PG_USERNAME; do sleep 1; done &> /dev/null
while ! PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -c "select * from meltano.alembic_version"; do sleep 1; done &> /dev/null

meltano "$@"