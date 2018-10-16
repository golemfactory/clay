#!/bin/sh

. ./golem_source__prep.sh

ID=99

echo "Running golem on network ${ID}"
python golemapp.py --protocol_id ${ID}

