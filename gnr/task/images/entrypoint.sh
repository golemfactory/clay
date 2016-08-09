#!/bin/bash

if [ "$LOCAL_USER_ID" != "" ]; then
    useradd --shell /bin/bash -u "$LOCAL_USER_ID" -o -c "" -m task
    export HOME=/home/task
    exec /usr/local/bin/gosu task /bin/sh -c "/usr/bin/python $@"
else
    /bin/sh -c "/usr/bin/python $@"
fi
