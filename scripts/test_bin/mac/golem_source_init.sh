#!/bin/sh

echo "WIP!!! This scripts does not install dependencies"
echo "golem_source_init: download git, setup python venv, taskcollector and docker"

PROJECT_DIR=~/projects

echo "Ensure projects directory exists"
mkdir -p ${PROJECT_DIR}

echo "Setup venv in ~/projects/golem-env"
python3 -m venv ${PROJECT_DIR}/golem-env

echo "Clone into ~/projects/golem"
git clone https://github.com/golemfactory/golem ${PROJECT_DIR}/golem

echo "Remember current directory"
CUR_DIR=$(pwd)

echo "Change directory to ~/projects/golem"
cd ${PROJECT_DIR}/golem

echo "Build taskcollector"
make -C apps/rendering/resources/taskcollector

echo "Run update from previous directory"
cd ${CUR_DIR}
./golem_source_update.sh
