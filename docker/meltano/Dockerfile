FROM meltano/meltano:v2.7.0-python3.9

ARG CODEARTIFACT_PIPY_URL
RUN pip install -U --index-url ${CODEARTIFACT_PIPY_URL} "gainy-compute<0.5.0"

RUN apt update && apt install -y postgresql-client libpq-dev netcat curl
RUN pip install pyyaml

ENV LC_ALL C.UTF-8

WORKDIR /project

COPY meltano.yml /project
COPY tap-eodhistoricaldata /tap-eodhistoricaldata
COPY tap-polygon /tap-polygon
COPY tap-coingecko /tap-coingecko
COPY target-algolia /target-algolia

RUN meltano install

RUN mkdir /init.d
COPY init.sh wait.sh /
RUN chmod +x /init.sh /wait.sh
