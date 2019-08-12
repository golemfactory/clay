#!/usr/bin/env bash
set -e

declare -r PYTHON=python3

function info_msg()
{
    echo -e "\e[92m$@\e[39m"
}

function install_runtime()
{
    code=$(cat <<EOC
import json

try:
    with open('$1', 'r') as f:
        config = json.load(f)
except:
    config = {}

if 'runtimes' not in config:
    config['runtimes'] = {}

if 'nvidia' not in config['runtimes']:
    config['runtimes']['nvidia'] = {
        'path': '/usr/bin/nvidia-container-runtime',
        'runtimeArgs': []
    }

with open('$1', 'w') as f:
    json.dump(config, f, sort_keys=True, indent=4)
# =================================================================
EOC
)

    sudo ${PYTHON} -c "${code}"
}

echo "Stopping   : docker-ce"
! sudo service docker stop > /dev/null 2>&1

! sudo apt-mark unhold nvidia-docker2 docker-ce > /dev/null 2>&1

echo "Removing   : nvidia-docker2"
! sudo apt-get purge -y nvidia-docker2 > /dev/null 2>&1

echo "Upgrading  : docker-ce"
! sudo apt-get update > /dev/null 2>&1
! sudo apt-get install -y docker-ce > /dev/null

echo "Installing : nvidia-container-toolkit"
! sudo apt-get install -y nvidia-container-toolkit > /dev/null

echo "Installing : nvidia runtime"
install_runtime /etc/docker/daemon.json

echo "Starting   : docker-ce"
! sudo service docker restart

info_msg "*** nvidia runtime installed successfully ***"
