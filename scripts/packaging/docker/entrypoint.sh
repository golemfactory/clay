#!/bin/bash

cd golem
git pull --rebase
pip install -r requirements.txt
python setup.py pack
cp build/*.zip /tmp
