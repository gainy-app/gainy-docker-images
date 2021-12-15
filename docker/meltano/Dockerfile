FROM meltano/meltano:v1.80.1-python3.8


RUN apt update
RUN apt install -y postgresql-client
RUN apt install -y awscli

RUN pip install pyyaml

WORKDIR /project

COPY meltano /project
COPY tap-eodhistoricaldata /tap-eodhistoricaldata
COPY target-algolia /target-algolia

RUN meltano install

COPY init.sh wait.sh /
RUN chmod +x /init.sh /wait.sh
