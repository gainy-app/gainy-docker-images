#!/bin/bash

while ! pg_isready -d $HASURA_GRAPHQL_DATABASE_URL; do sleep 1; done &> /dev/null

sed -i "s/schema: public\w*$/schema: $HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME/" metadata/*

MIGRATION_DIRS=()
while read -r i; do
  FILENAME=$(basename "$i")
  MIGRATION_NAME="$(date '+%s')${FILENAME%.sql}"
  MIGRATION_DIR="migrations/$MIGRATION_NAME"

  MIGRATION_DIRS+=( "$MIGRATION_DIR" )
  mkdir -p "$MIGRATION_DIR"

## TODO:deployment_v2:versioned hasura views lambdas blocked by versioned lambdas
#  ORIGINAL_CREATE_VIEW_STATEMENT="$(cat "$i" | tr '\n' ' ' | grep -oiP 'create[a-z ]*view[a-z."_ ]*?as')"
#  ORIGINAL_VIEW_NAME="$(echo $ORIGINAL_CREATE_VIEW_STATEMENT | grep -io '["a-z_]*\s*as' | awk '{print $1}' | tr -d '"')"
#  VERSIONED_VIEW_NAME="${HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME//public/}_$ORIGINAL_VIEW_NAME"
#  VERSIONED_CREATE_VIEW_STATEMENT="${ORIGINAL_CREATE_VIEW_STATEMENT//$ORIGINAL_VIEW_NAME/$VERSIONED_VIEW_NAME}"
#  sed -e "s/$ORIGINAL_CREATE_VIEW_STATEMENT/$VERSIONED_CREATE_VIEW_STATEMENT/" \

  sed -Ee "s/\"?public\"?\./\"$HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME\"./g" "$i" | tee "migrations/$MIGRATION_NAME/up.sql"

  echo '*' > "migrations/$MIGRATION_NAME/.gitignore"
done <<< $(find shared_views -iname '*.sql' | sort)

# starting tmp server for migrations and metadata apply
LOCKFILE=/run/graphql-engine.pid
( nohup graphql-engine serve --server-port 8080 2>&1 & echo $! > $LOCKFILE ) > /proc/1/fd/1 &
sleep 5

echo hasura migrate apply
if ! hasura migrate apply; then
  rm -rf ${MIGRATION_DIRS[@]}
  exit 1
fi

rm -rf ${MIGRATION_DIRS[@]}

echo hasura metadata apply
if ! hasura metadata apply; then
  echo hasura metadata apply failed, sleeping
  sleep 60
  exit 1
fi

kill $(cat $LOCKFILE)

graphql-engine serve --server-port 8080