#!/bin/bash

while ! pg_isready -d $HASURA_GRAPHQL_DATABASE_URL; do sleep 1; done &> /dev/null

sed -i "s/schema: public\w*$/schema: $HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME/" metadata/*

### TODO:deployment_v2:versioned hasura views lambdas blocked by versioned lambdas

# starting tmp server for migrations and metadata apply
LOCKFILE=/run/graphql-engine.pid
( nohup graphql-engine serve --server-port 8080 2>&1 & echo $! > $LOCKFILE ) > /proc/1/fd/1 &
sleep 5

echo hasura migrate apply
hasura migrate apply || exit 1

if [ "$ENV" = "local" ]; then
  echo 'Importing seeds'
  find seeds -iname '*.sql' | sort | while read -r i; do
    psql -d $HASURA_GRAPHQL_DATABASE_URL -P pager -f "$i"
  done
  echo "Seeding done"
fi

for (( ATTEMPT=0; ATTEMPT<10; ATTEMPT++ )); do
  if curl -s http://$MELTANO_AIRFLOW_SCHEDULER_HOST:$MELTANO_AIRFLOW_SCHEDULER_PORT/; then
    break;
  fi

  sleep 10;
done

echo hasura metadata apply
if ! hasura metadata apply; then
  echo hasura metadata apply failed, sleeping
  sleep 60
  exit 1
fi

kill $(cat $LOCKFILE)

graphql-engine serve --server-port 8080