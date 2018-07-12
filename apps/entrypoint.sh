#!/bin/bash

LOADER=

while getopts ":l" opt; do
  case $opt in
    l)
      LOADER=$OPTARG
      shift && shift
      ;;
  esac
done

if [ "$LOCAL_USER_ID" != "" ]; then
    useradd --shell /bin/bash -u "$LOCAL_USER_ID" -o -c "" -m task
    export HOME=/home/task
    exec /usr/local/bin/su-exec task /bin/sh -c "${LOADER} /usr/bin/python $@"
elif [ "$OSX_USER" != "" ]; then
    OSX_USER_ID=$(ls -n /golem | grep work | sed 's/\s\s*/ /g' | cut -d' ' -f3)
    useradd --shell /bin/bash -u "$OSX_USER_ID" -o -c "" -m task
    export HOME=/home/task
    exec /usr/local/bin/su-exec task /bin/sh -c "${LOADER} /usr/bin/python $@"
else
    ${LOADER} /usr/bin/python $@
fi
