FROM python:3.8

# Install poetry
ENV POETRY_VERSION=1.1.12

RUN pip install --upgrade pip
RUN pip install "poetry==$POETRY_VERSION"

# Init wordir and install dependencies
WORKDIR /tap-eodhistoricaldata
COPY . /tap-eodhistoricaldata/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

CMD [ "poetry", "run", "pytest"]