#!/bin/bash

sed -i "s/schema: public\w*$/schema: $HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME/" metadata/*

MIGRATION_DIRS=()
find shared_views -iname '*.sql' | sort | while read -r i; do
  FILENAME=$(basename "$i")
  MIGRATION_NAME="$(date '+%s')${FILENAME%.sql}"
  MIGRATION_DIR="migrations/$MIGRATION_NAME"

  MIGRATION_DIRS+=( "$MIGRATION_DIR" )
  mkdir -p "$MIGRATION_DIR"

## TODO: views versioning (currently blocked by lambdas)
#  ORIGINAL_CREATE_VIEW_STATEMENT="$(cat "$i" | tr '\n' ' ' | grep -oiP 'create[a-z ]*view[a-z."_ ]*?as')"
#  ORIGINAL_VIEW_NAME="$(echo $ORIGINAL_CREATE_VIEW_STATEMENT | grep -io '["a-z_]*\s*as' | awk '{print $1}' | tr -d '"')"
#  VERSIONED_VIEW_NAME="${HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME//public/}_$ORIGINAL_VIEW_NAME"
#  VERSIONED_CREATE_VIEW_STATEMENT="${ORIGINAL_CREATE_VIEW_STATEMENT//$ORIGINAL_VIEW_NAME/$VERSIONED_VIEW_NAME}"
#  sed -e "s/$ORIGINAL_CREATE_VIEW_STATEMENT/$VERSIONED_CREATE_VIEW_STATEMENT/" \

  sed -e "s/public\./$HASURA_GRAPHQL_PUBLIC_SCHEMA_NAME./g" "$i" | tee "migrations/$MIGRATION_NAME/up.sql"

  echo '*' > "migrations/$MIGRATION_NAME/.gitignore"
done

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
hasura metadata apply || exit 1

kill $(cat $LOCKFILE)

graphql-engine serve --server-port 8080