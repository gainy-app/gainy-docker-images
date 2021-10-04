export PARAMS ?= $(filter-out $@,$(MAKECMDGOALS))

IMAGE_BASE := 217303665077.dkr.ecr.us-east-1.amazonaws.com/gainy

GITHUB_REF ?= latest
ifeq (${GITHUB_REF:refs/tags/%=},)
	GITHUB_TAG := ${GITHUB_REF:refs/tags/%=%}
	IMAGE_TAG ?= ${GITHUB_TAG}
endif
ifeq (${GITHUB_REF:refs/heads/%=},)
	GITHUB_BRANCH := ${GITHUB_REF:refs/heads/%=%}
	IMAGE_TAG ?= ${GITHUB_BRANCH}
endif

all: help;
default: help;

build-meltano:
	docker build --rm --no-cache -t ${IMAGE_BASE}-meltano:${IMAGE_TAG} docker/meltano

publish-meltano:
	docker image push ${IMAGE_BASE}-meltano:${TAG}

build-firebase:
	docker build --rm --no-cache -t ${IMAGE_BASE}-firebase:${IMAGE_TAG} docker/firebase

publish-firebase:
	docker image push ${IMAGE_BASE}-firebase:${TAG}

build-hasura:
	docker build --rm --no-cache -t ${IMAGE_BASE}-hasura:${IMAGE_TAG} docker/hasura

publish-hasura:
	docker image push ${IMAGE_BASE}-hasura:${IMAGE_TAG}

build: build-meltano build-firebase build-hasura

publish: publish-meltano publish-firebase publish-hasura

%:
	@:
