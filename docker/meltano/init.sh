#!/bin/bash

python scripts/generate_meltano_config.py $ENV
( cd scripts && python3 generate_rules_sql.py )

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_HOST -p $PG_PORT -U $PG_USERNAME; do sleep 1; done
echo 'Importing seeds'
find seed seed/$ENV -maxdepth 1 -iname '*.sql' | sort | while read -r i; do
  PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -P pager -f "$i"
done

PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -c \
  "insert into deployment.public_schemas(schema_name, deployed_at) values ('$DBT_TARGET_SCHEMA', now()) on conflict(schema_name) do update set deployed_at = excluded.deployed_at;"

PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -c "CREATE SCHEMA IF NOT EXISTS $DBT_TARGET_SCHEMA;"

# Function: CDF of Normal Gaussian Distribution (mu=0,sigma=1, (so prestandardize input))
PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -c "CREATE OR REPLACE FUNCTION $DBT_TARGET_SCHEMA.pnorm(z double precision) RETURNS double precision AS \$\$
                                                                                    SELECT CASE -- calculation by erf-function expansion to series (error= +/-2e-7, const 0 if <-7 AND 1 if >7)
                                                                                               when \$1 <-1e4 then 0.0 when \$1 >1e4 then 1.0
                                                                                               when \$1 >= 0 then 1 - POWER(((((((0.000005383*\$1+0.0000488906)*\$1+0.0000380036)*\$1+0.0032776263)*\$1+0.0211410061)*\$1+0.049867347)*\$1+1),-16)/2
                                                                                               else 1 - $DBT_TARGET_SCHEMA.pnorm(-\$1)
                                                                                               END;
                                                                                    \$\$ LANGUAGE SQL IMMUTABLE STRICT;"

if ! PGPASSWORD=$PG_PASSWORD psql -h $PG_HOST -p $PG_PORT -U $PG_USERNAME $PG_DBNAME -c "select count(*) from $DBT_TARGET_SCHEMA.deployment_metadata"; then
  echo 'Running csv-to-postgres' && meltano schedule run csv-to-postgres --force
else
  RUNNING_DEPLOYMENT_JOBS_COUNT=$(meltano invoke airflow dags list-runs -d deployment --state running | wc -l)
  if (( RUNNING_DEPLOYMENT_JOBS_COUNT < 3 )); then
    nohup bash -c "meltano invoke airflow dags trigger deployment" &> /dev/null &
  fi
fi

echo "Seeding done"

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

export TAP_POSTGRES_SYNC_FUNDAMENTALS_HOST="$TAP_POSTGRES_SYNC_HOST"
export TAP_POSTGRES_SYNC_FUNDAMENTALS_PORT="$TAP_POSTGRES_SYNC_PORT"
export TAP_POSTGRES_SYNC_FUNDAMENTALS_USER="$TAP_POSTGRES_SYNC_USER"
export TAP_POSTGRES_SYNC_FUNDAMENTALS_PASSWORD="$TAP_POSTGRES_SYNC_PASSWORD"
export TAP_POSTGRES_SYNC_FUNDAMENTALS_DBNAME="$TAP_POSTGRES_SYNC_DBNAME"
export TAP_POSTGRES_SYNC_FUNDAMENTALS_FILTER_SCHEMAS="$TAP_POSTGRES_SYNC_FILTER_SCHEMAS"

export TAP_POSTGRES_SYNC_OPTIONS_HOST="$TAP_POSTGRES_SYNC_HOST"
export TAP_POSTGRES_SYNC_OPTIONS_PORT="$TAP_POSTGRES_SYNC_PORT"
export TAP_POSTGRES_SYNC_OPTIONS_USER="$TAP_POSTGRES_SYNC_USER"
export TAP_POSTGRES_SYNC_OPTIONS_PASSWORD="$TAP_POSTGRES_SYNC_PASSWORD"
export TAP_POSTGRES_SYNC_OPTIONS_DBNAME="$TAP_POSTGRES_SYNC_DBNAME"
export TAP_POSTGRES_SYNC_OPTIONS_FILTER_SCHEMAS="$TAP_POSTGRES_SYNC_FILTER_SCHEMAS"

export TARGET_POSTGRES_SMALL_BATCH_HOST="$TARGET_POSTGRES_HOST"
export TARGET_POSTGRES_SMALL_BATCH_PORT="$TARGET_POSTGRES_PORT"
export TARGET_POSTGRES_SMALL_BATCH_USER="$TARGET_POSTGRES_USER"
export TARGET_POSTGRES_SMALL_BATCH_PASSWORD="$TARGET_POSTGRES_PASSWORD"
export TARGET_POSTGRES_SMALL_BATCH_DBNAME="$TARGET_POSTGRES_DBNAME"
export TARGET_POSTGRES_SMALL_BATCH_SCHEMA="$TARGET_POSTGRES_SCHEMA"

meltano "$@"
