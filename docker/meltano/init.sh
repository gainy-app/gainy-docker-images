#!/bin/bash

python scripts/generate_meltano_config.py $ENV
( cd scripts && python3 generate_rules_sql.py )

# INSTALL `gainy-compute`
GAINY_COMPUTE_VERSION=0.1.3

CODEARTIFACT_AUTH_TOKEN=`aws codeartifact get-authorization-token --domain gainy-app --query authorizationToken --output text`
CODEARTIFACT_REPOSITORY_URL=https://aws:$CODEARTIFACT_AUTH_TOKEN@gainy-app-217303665077.d.codeartifact.us-east-1.amazonaws.com/pypi/gainy-app/simple

pip config set global.index-url $CODEARTIFACT_REPOSITORY_URL
pip install gainy-compute==$GAINY_COMPUTE_VERSION


while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME; do sleep 1; done
echo 'Importing seeds'
find seed -iname '*.sql' | sort | while read -r i; do
  PGPASSWORD=$PG_PASSWORD psql -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME $PG_DATABASE -P pager -f "$i"
done
PGPASSWORD=$PG_PASSWORD psql -h $PG_ADDRESS -p $PG_PORT -U $PG_USERNAME $PG_DATABASE -c "CREATE SCHEMA IF NOT EXISTS $DBT_TARGET_SCHEMA;"
echo "Seeding done"

echo 'Running csv-to-postgres' && meltano schedule run csv-to-postgres --force --transform skip
echo 'Creating snapshot' && meltano invoke dbt snapshot
echo 'Running transformations' && meltano invoke dbt run

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

if [ "$ENV" == "local" ]; then
  meltano invoke dbt docs generate
fi

meltano invoke airflow pools set dbt 1 dbt

meltano "$@"