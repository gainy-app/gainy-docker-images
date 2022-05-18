FROM python:3.9-slim-buster as dev

# Install poetry
ENV POETRY_VERSION=1.1.12

RUN apt update && apt install -y gcc

RUN pip install --upgrade pip
RUN pip install "poetry==$POETRY_VERSION"

# Init wordir and install dependencies
COPY . /tap-coingecko/
WORKDIR /tap-coingecko/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

FROM dev as test
# Run tests
WORKDIR /tap-coingecko/tests/
CMD [ "poetry", "run", "pytest"]
