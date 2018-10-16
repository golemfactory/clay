#!/bin/sh

_CONF_NAME=".bin_config.sh"
_SCRIPT_DIR=$( dirname "${BASH_SOURCE[0]}" )

# Current dir => home dir => script dir
_CONFIG_OPTIONS="./${_CONF_NAME}
${HOME}/${_CONF_NAME}
${_SCRIPT_DIR}/${_CONF_NAME}"

for CONFIG in ${_CONFIG_OPTIONS}
do
	echo "Checking $CONFIG"
	if [ -f "$CONFIG" ]; then
		echo EXISTS
		. $CONFIG
		break
	fi
	echo "Not there"
done

