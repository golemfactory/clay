#!/bin/sh

. ./golem_source__prep.sh

echo "Install requirements"
pip install -r requirements.txt

echo "Run setup.py develop"
python setup.py develop

read -p "Press any key to continue..."

