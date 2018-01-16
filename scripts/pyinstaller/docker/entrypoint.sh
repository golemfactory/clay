#!/bin/bash

set -e

cd golem
git stash && git pull --rebase

pip install -r requirements.txt
python setup.py pyinstaller
cp -r dist/* /tmp

echo "-------------------------------------"
echo "Package location: /tmp/golem[app,cli]"
echo "-------------------------------------"
