export PARAMS ?= $(filter-out $@,$(MAKECMDGOALS))

-include .env.make

GITHUB_REF ?= latest
ifeq (${GITHUB_REF:refs/tags/%=},)
	GITHUB_TAG := ${GITHUB_REF:refs/tags/%=%}
	IMAGE_TAG ?= ${GITHUB_TAG}
endif
ifeq (${GITHUB_REF:refs/heads/%=},)
	GITHUB_BRANCH := ${GITHUB_REF:refs/heads/%=%}
	IMAGE_TAG ?= ${GITHUB_BRANCH}
endif
IMAGE_TAG ?= "latest"

all: help;
default: help;

test:
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml build --force-rm test-tap-eodhistoricaldata
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml run test-tap-eodhistoricaldata
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml build --force-rm test-tap-polygon
	docker-compose -p gainy-docker-images-test -f docker-compose.test.yml run test-tap-polygon
	make test-clean

test-clean:
	docker-compose -p gainy_test -f docker-compose.test.yml rm -sv

build-meltano:
	docker build --rm --no-cache -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-meltano:${IMAGE_TAG} docker/meltano

publish-meltano:
	docker image push ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-meltano:${IMAGE_TAG}

build-firebase:
	docker build --rm --no-cache -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-firebase:${IMAGE_TAG} docker/firebase

publish-firebase:
	docker image push ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-firebase:${IMAGE_TAG}

build-hasura:
	docker build --rm --no-cache -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-hasura:${IMAGE_TAG} docker/hasura

publish-hasura:
	docker image push ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-hasura:${IMAGE_TAG}

build-lambda-python:
	docker build --rm --no-cache -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-lambda-python:${IMAGE_TAG} docker/lambda-python

publish-lambda-python:
	docker image push ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-lambda-python:${IMAGE_TAG}

build: build-meltano build-firebase build-hasura build-lambda-python

publish: publish-meltano publish-firebase publish-hasura publish-lambda-python

%:
	@:
