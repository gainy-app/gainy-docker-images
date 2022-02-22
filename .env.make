export BASE_IMAGE_REGISTRY_ADDRESS="217303665077.dkr.ecr.us-east-1.amazonaws.com"

# CODEARTIFACT
CODEARTIFACT_AUTH_TOKEN=$(shell aws codeartifact get-authorization-token --domain gainy-app --query authorizationToken --output text)
CODEARTIFACT_REPO_URL=$(shell aws codeartifact get-repository-endpoint --domain gainy-app --repository gainy-app --format pypi --query repositoryEndpoint --output text | sed "s/https:\/\///g" )
export CODEARTIFACT_PIPY_URL="https://aws:${CODEARTIFACT_AUTH_TOKEN}@${CODEARTIFACT_REPO_URL}simple/"