ARG CODEARTIFACT_PIPY_URL

FROM meltano/meltano:v1.90.1-python3.8

RUN apt update && apt install -y postgresql-client
RUN pip install pyyaml

COPY requirements.txt /requirements.txt
RUN pip install --requirement /requirements.txt --index-url ${CODEARTIFACT_PIPY_URL}

WORKDIR /project

COPY meltano /project
COPY tap-eodhistoricaldata /tap-eodhistoricaldata
COPY tap-polygon /tap-polygon
COPY target-algolia /target-algolia

RUN meltano install

COPY init.sh wait.sh /
RUN chmod +x /init.sh /wait.sh