FROM meltano/meltano:v1.95.0-python3.8

ARG CODEARTIFACT_PIPY_URL
RUN pip install -U --index-url ${CODEARTIFACT_PIPY_URL} gainy-compute

RUN apt update && apt install -y postgresql-client
RUN pip install pyyaml

ENV LC_ALL C.UTF-8

WORKDIR /project

COPY meltano /project
COPY tap-eodhistoricaldata /tap-eodhistoricaldata
COPY tap-polygon /tap-polygon
COPY target-algolia /target-algolia

RUN meltano install

COPY init.sh wait.sh /
RUN chmod +x /init.sh /wait.sh
