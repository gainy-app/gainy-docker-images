#!/bin/bash

for i in /usr/lib/postgresql/*/bin; do
  export PATH=$PATH:$i
done

while ! pg_isready -d $HASURA_GRAPHQL_DATABASE_URL; do sleep 1; done &> /dev/null

python3 generate_config.py

# starting tmp server for migrations and metadata apply
export HASURA_GRAPHQL_SERVER_PORT=8081
export HASURA_GRAPHQL_ENDPOINT=http://localhost:$HASURA_GRAPHQL_SERVER_PORT
LOCKFILE=/run/graphql-engine.pid
( nohup graphql-engine serve 2>&1 & echo $! > $LOCKFILE ) > /proc/1/fd/1 &

echo hasura migrate apply
for (( ATTEMPT=0; ATTEMPT<10; ATTEMPT++ )); do
  if ! curl -s "$HASURA_GRAPHQL_ENDPOINT/healthz" | grep OK > /dev/null; then
    sleep 6;
    continue;
  fi

  if hasura migrate apply --skip-update-check; then
    break
  fi

  echo hasura migrate apply failed, sleeping
  sleep 6
done

echo hasura metadata apply
for (( ATTEMPT=0; ATTEMPT<60; ATTEMPT++ )); do
  if hasura metadata apply --skip-update-check; then
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

# TODO: install extension for public schema
if [ "$HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME" != "public" ]; then
  psql -d $HASURA_GRAPHQL_DATABASE_URL -P pager -c "CREATE OR REPLACE FUNCTION app.gen_random_uuid() RETURNS uuid AS \$\$ DECLARE id uuid; BEGIN RETURN public.gen_random_uuid(); END; \$\$ LANGUAGE plpgsql;"
  psql -d $HASURA_GRAPHQL_DATABASE_URL -P pager -c "CREATE OR REPLACE FUNCTION $HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME.gen_random_uuid() RETURNS uuid AS \$\$ DECLARE id uuid; BEGIN RETURN public.gen_random_uuid(); END; \$\$ LANGUAGE plpgsql;"
fi

if [ "$ENV" = "local" ]; then
  echo 'Importing seeds'
  find seeds -iname '*.sql' | sort | while read -r i; do
    psql -d "$HASURA_GRAPHQL_DATABASE_URL?options=-csearch_path%3D$HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME" -P pager -f "$i"
  done
  echo "Seeding done"
fi

kill $(cat $LOCKFILE)

export HASURA_GRAPHQL_SERVER_PORT=8080
export HASURA_GRAPHQL_ENDPOINT=http://localhost:$HASURA_GRAPHQL_SERVER_PORT
graphql-engine serve
