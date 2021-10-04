FROM meltano/meltano:v1.80.1-python3.8

RUN apt update && apt install -y postgresql-client
RUN pip install pyyaml

WORKDIR /project

COPY meltano /project
COPY tap-eodhistoricaldata /tap-eodhistoricaldata

RUN meltano install

COPY init.sh wait.sh /
RUN chmod +x /init.sh /wait.sh
