export PARAMS ?= $(filter-out $@,$(MAKECMDGOALS))

-include .env.make

IMAGE_TAG ?= "latest"
PLATFORMS ?= "linux/amd64"
BUILD_FLAGS ?= "--load"

all: help;
default: help;

shell:
	@echo 'Choose service: tap-eodhistoricaldata tap-polygon tap-coingecko'
	@echo -n 'Service: ' && read service && echo $${service} && docker-compose run --use-aliases --rm $${service} /bin/bash

style-check:
	yapf --diff -r docker

style-fix:
	yapf -i -r docker

test-eod:
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml build --force-rm test-tap-eodhistoricaldata
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml run --rm test-tap-eodhistoricaldata

test-polygon:
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml build --force-rm test-tap-polygon
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml run --rm test-tap-polygon

test-coingecko:
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml build --force-rm test-tap-coingecko
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml run --rm test-tap-coingecko

test-clean:
	docker-compose -p gainy_test -f docker-compose.test.yml rm -sv

test: test-eod test-polygon test-coingecko test-clean

build-meltano:
	docker buildx build --cache-from "type=gha" --cache-to "type=gha" --platform="${PLATFORMS}" --rm ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-meltano:${IMAGE_TAG} --build-arg CODEARTIFACT_PIPY_URL=${CODEARTIFACT_PIPY_URL} docker/meltano

build-hasura:
	docker buildx build --cache-from "type=gha" --cache-to "type=gha" --platform="${PLATFORMS}" --rm ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-hasura:${IMAGE_TAG} docker/hasura

build-lambda-python:
	docker buildx build --cache-from "type=gha" --cache-to "type=gha" --platform="${PLATFORMS}" --rm ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-lambda-python:${IMAGE_TAG} --build-arg CODEARTIFACT_PIPY_URL=${CODEARTIFACT_PIPY_URL} docker/lambda-python

build: build-meltano build-hasura build-lambda-python

%:
	@:
