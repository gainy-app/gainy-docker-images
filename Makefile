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

build-meltano:
	docker build --rm --no-cache -t ${BASE_IMAGE_PREFIX}-meltano:${IMAGE_TAG} docker/meltano

publish-meltano:
	docker image push ${BASE_IMAGE_PREFIX}-meltano:${IMAGE_TAG}

build-firebase:
	docker build --rm --no-cache -t ${BASE_IMAGE_PREFIX}-firebase:${IMAGE_TAG} docker/firebase

publish-firebase:
	docker image push ${BASE_IMAGE_PREFIX}-firebase:${IMAGE_TAG}

build-hasura:
	docker build --rm --no-cache -t ${BASE_IMAGE_PREFIX}-hasura:${IMAGE_TAG} docker/hasura

publish-hasura:
	docker image push ${BASE_IMAGE_PREFIX}-hasura:${IMAGE_TAG}

build: build-meltano build-firebase build-hasura

publish: publish-meltano publish-firebase publish-hasura

%:
	@:
