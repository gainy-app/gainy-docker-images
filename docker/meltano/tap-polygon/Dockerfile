FROM python:3.9-slim-buster as dev

RUN apt update && apt install -y gcc

RUN pip install --upgrade pip poetry

# Init wordir and install dependencies
COPY . /tap-polygon/
WORKDIR /tap-polygon/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

FROM dev as test
# Run tests
WORKDIR /tap-polygon/tests/
CMD [ "poetry", "run", "pytest"]
