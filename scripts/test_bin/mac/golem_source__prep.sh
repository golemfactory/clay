#!/bin/sh

PROJECT_DIR=~/projects

echo "Activate golem-env"
. ${PROJECT_DIR}/golem-env/bin/activate

echo "Change to source directory"
cd ${PROJECT_DIR}/golem

echo "Load docker env"

DOCKER_STATUS=$(docker-machine status golem)
if [ "$DOCKER_STATUS" != "Running" ]
then
    docker-machine restart golem || exit 1
fi
eval $(docker-machine env golem)

