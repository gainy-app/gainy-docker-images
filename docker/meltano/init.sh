#!/bin/bash

for i in /usr/lib/postgresql/*/bin; do
  export PATH=$PATH:$i
done

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_HOST -p $PG_PORT -U $PG_USERNAME; do sleep 1; done

while read -r i; do
  chmod +x $i
  if ! $i && [ "$ENV" != "local" ]; then
    exit 1
  fi
done < <(find /init.d -maxdepth 1 -type f | sort)

meltano "$@"
