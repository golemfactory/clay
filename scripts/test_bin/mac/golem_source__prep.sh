#!/bin/sh

PROJECT_DIR=~/projects

echo "Activate golem-env"
. ${PROJECT_DIR}/golem-env/bin/activate

echo "Change to source directory"
cd ${PROJECT_DIR}/golem

echo "Load docker env"
docker-machine restart golem || exit 1
eval $(docker-machine env golem)

