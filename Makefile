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
ifdef PRERELEASE
	IMAGE_TAG := ${IMAGE_TAG}-$(shell date '+%s')
endif

PLATFORMS ?= "linux/amd64"
BUILD_FLAGS ?= "--load"

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

build-status:
	echo "Building tag ${IMAGE_TAG}"

build-meltano:
	docker buildx build --platform="${PLATFORMS}" --rm --no-cache ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-meltano:${IMAGE_TAG} --build-arg CODEARTIFACT_PIPY_URL=${CODEARTIFACT_PIPY_URL} docker/meltano

build-firebase:
	docker buildx build --platform="${PLATFORMS}" --rm --no-cache ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-firebase:${IMAGE_TAG} docker/firebase

build-hasura:
	docker buildx build --platform="${PLATFORMS}" --rm --no-cache ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-hasura:${IMAGE_TAG} docker/hasura

build-lambda-python:
	docker buildx build --platform="${PLATFORMS}" --rm --no-cache ${BUILD_FLAGS} -t ${BASE_IMAGE_REGISTRY_ADDRESS}/gainy-lambda-python:${IMAGE_TAG} --build-arg CODEARTIFACT_PIPY_URL=${CODEARTIFACT_PIPY_URL} docker/lambda-python

build: build-status build-meltano build-firebase build-hasura build-lambda-python

%:
	@:
