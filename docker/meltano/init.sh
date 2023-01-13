#!/bin/bash

for i in /usr/lib/postgresql/*/bin; do
  export PATH=$PATH:$i
done

while ! PGPASSWORD=$PG_PASSWORD pg_isready -h $PG_HOST -p $PG_PORT -U $PG_USERNAME; do sleep 1; done

find /init.d -maxdepth 1 -type f | sort | while read -r i; do
  chmod +x $i
  $i || exit 1
done

meltano "$@"
