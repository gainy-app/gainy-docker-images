FROM hasura/graphql-engine:v2.16.1

RUN apt update && apt install -y curl postgresql-client python3-pip

COPY /requirements.txt /requirements.txt
RUN pip3 install -r requirements.txt
RUN curl -L https://github.com/hasura/graphql-engine/raw/stable/cli/get.sh | bash

WORKDIR /hasura

ENV HASURA_GRAPHQL_MIGRATIONS_DIR=/hasura/migrations
ENV HASURA_GRAPHQL_METADATA_DIR=/hasura/metadata

COPY /init.sh /init.sh

ENTRYPOINT ["/init.sh"]
