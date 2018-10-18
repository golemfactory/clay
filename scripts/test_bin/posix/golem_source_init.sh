#!/bin/sh

echo "WIP!!! This scripts does not install dependencies"
echo "golem_source_init: download git, setup python venv, taskcollector and docker"

echo "Loading config"
_SCRIPT_DIR=$( dirname "${BASH_SOURCE[0]}" )
. "${_SCRIPT_DIR}/_load_config.sh"

echo "Ensure projects directory exists"
mkdir -p "${PROJECT_DIR}"

echo "Setup venv in ~/projects/golem-env"
python3 -m venv "${VENV_DIR}"

echo "Clone into ~/projects/golem"
git clone https://github.com/golemfactory/golem "${GOLEM_SRC_DIR}"

echo "Remember current directory"
CUR_DIR=$(pwd)

echo "Change directory to ~/projects/golem"
cd "${GOLEM_SRC_DIR}"

echo "Build taskcollector"
make -C apps/rendering/resources/taskcollector

echo "Run update from previous directory"
cd "${CUR_DIR}"
./golem_source_update.sh
