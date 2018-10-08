#!/bin/sh

echo "WIP!!! This scripts does not install dependencies"
echo "golem_source_init: download git, setup python venv, taskcollector and docker"

_CONF_NAME=".bin_config.sh"
_CUR_DIR=$( dirname "${BASH_SOURCE[0]}" )

# Current dir => home dir => script dir
_CONFIG_OPTIONS="./${_CONF_NAME}
~/${_CONF_NAME}
${_CUR_DIR}/${_CONF_NAME}"

for CONFIG in ${_CONFIG_OPTIONS}; do
	echo "Checking $CONFIG"
	if [ -f $CONFIG ]; then
		echo EXISTS
		. $CONFIG
		break
	fi
	echo "Not there"
done

echo "Ensure projects directory exists"
mkdir -p ${PROJECT_DIR}

echo "Setup venv in ~/projects/golem-env"
python3 -m venv ${VENV_DIR}

echo "Clone into ~/projects/golem"
git clone https://github.com/golemfactory/golem ${GOLEM_SRC_DIR}

echo "Remember current directory"
CUR_DIR=$(pwd)

echo "Change directory to ~/projects/golem"
cd ${GOLEM_SRC_DIR}

echo "Build taskcollector"
make -C apps/rendering/resources/taskcollector

echo "Run update from previous directory"
cd ${CUR_DIR}
./golem_source_update.sh
