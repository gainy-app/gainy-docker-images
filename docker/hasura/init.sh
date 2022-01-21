#!/bin/bash

while ! pg_isready -d $HASURA_GRAPHQL_DATABASE_URL; do sleep 1; done &> /dev/null

sed -i "s/schema: public\w*$/schema: $HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME/" metadata/*

### TODO:deployment_v2:versioned hasura views lambdas blocked by versioned lambdas

# starting tmp server for migrations and metadata apply
export HASURA_GRAPHQL_SERVER_PORT=8081
export HASURA_GRAPHQL_ENDPOINT=http://localhost:$HASURA_GRAPHQL_SERVER_PORT
LOCKFILE=/run/graphql-engine.pid
( nohup graphql-engine serve 2>&1 & echo $! > $LOCKFILE ) > /proc/1/fd/1 &
sleep 20

curl -v $HASURA_GRAPHQL_ENDPOINT
curl -v $HASURA_GRAPHQL_ENDPOINT/healthz
curl -vH "x-hasura-admin-secret: $HASURA_GRAPHQL_ADMIN_SECRET" $HASURA_GRAPHQL_ENDPOINT/healthz

echo hasura migrate apply
hasura migrate apply || exit 1

echo hasura metadata apply
for (( ATTEMPT=0; ATTEMPT<30; ATTEMPT++ )); do
  if hasura metadata apply; then
    break
  fi

  echo hasura metadata apply failed, sleeping
  sleep 60
done

# Dirty hack around an issue with hasura not migrating rest endpoints
# https://github.com/hasura/graphql-engine/issues/7898
REST_ENDPOINTS_METADATA_FILE=metadata/rest_endpoints.yaml

if test -f "$REST_ENDPOINTS_METADATA_FILE"; then
  REST_ENDPOINTS_METADATA="$(python3 -c 'import sys, yaml, json; y=yaml.safe_load(sys.stdin.read()); print(json.dumps(y))' < "$REST_ENDPOINTS_METADATA_FILE")"
  psql -d $HASURA_GRAPHQL_DATABASE_URL -P pager -c "UPDATE hdb_catalog.hdb_metadata SET metadata = jsonb_insert(metadata::jsonb, '{rest_endpoints}', '$REST_ENDPOINTS_METADATA'::jsonb, false)"
fi

if [ "$ENV" = "local" ]; then
  echo 'Importing seeds'
  find seeds -iname '*.sql' | sort | while read -r i; do
    psql -d $HASURA_GRAPHQL_DATABASE_URL -P pager -f "$i"
  done
  echo "Seeding done"
fi

kill $(cat $LOCKFILE)

export HASURA_GRAPHQL_SERVER_PORT=8080
export HASURA_GRAPHQL_ENDPOINT=http://localhost:$HASURA_GRAPHQL_SERVER_PORT
graphql-engine serve
