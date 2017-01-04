#!/bin/bash

set -e

cd golem
git stash && git pull --rebase
source scripts/packaging/docker/patch.sh

pip install -r requirements.txt
python setup.py pack
cp build/golem-linux.zip /tmp

echo "--------------------------------------"
echo "Package location: /tmp/golem-linux.zip"
echo "--------------------------------------"
