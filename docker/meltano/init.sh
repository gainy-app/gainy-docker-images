#!/bin/bash

python scripts/generate_meltano_config.py $ENV

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME; do sleep 1; done
echo 'Importing seeds'
find seed -iname '*.sql' | while read -r i; do
  PGPASSWORD=$PG_PASSWORD psql -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME $PG_DATABASE -P pager -f "$i"
done
echo "Seeding done"
PGPASSWORD=$PG_PASSWORD psql -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME $PG_DATABASE -P pager -c "select count(*) from tickers" &> /dev/null || (echo 'Running cst-to-postgres' && meltano schedule run csv-to-postgres)

if [ -z "$NO_AIRFLOW" ]; then
  if ! meltano invoke airflow users list | grep admin > /dev/null; then
    echo "Creating admin user"
    meltano invoke airflow users create --username admin --password "$AIRFLOW_PASSWORD" --firstname admin --lastname admin --role Admin --email support@gainy.app
  else
    echo "Admin user exists"
  fi
else
  echo "Skip creating admin"
fi

( cd scripts && python3 generate_rules_sql.py )

meltano "$@"