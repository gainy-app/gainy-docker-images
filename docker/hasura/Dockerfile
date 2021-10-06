FROM hasura/graphql-engine:v2.0.9.cli-migrations-v2

RUN apt update
RUN apt install -y curl
RUN curl -L https://github.com/hasura/graphql-engine/raw/stable/cli/get.sh | bash

WORKDIR /hasura

ENV HASURA_GRAPHQL_MIGRATIONS_DIR=/hasura/migrations
ENV HASURA_GRAPHQL_METADATA_DIR=/hasura/metadata
ENV HASURA_PORT=8080

CMD graphql-engine serve --server-port $HASURA_PORT