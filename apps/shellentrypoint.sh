#!/bin/bash

if [ "$LOCAL_USER_ID" != "" ]; then
    useradd --shell /bin/bash -u "$LOCAL_USER_ID" -o -c "" -m task
    export HOME=/home/task
    /bin/chmod +x /golem/resources/start.sh
    exec /usr/local/bin/su-exec task /golem/resources/start.sh
elif [ "$OSX_USER" != "" ]; then
    OSX_USER_ID=$(ls -n /golem | grep work | sed 's/\s\s*/ /g' | cut -d' ' -f3)
    useradd --shell /bin/bash -u "$OSX_USER_ID" -o -c "" -m task
    export HOME=/home/task
    /bin/chmod +x /golem/resources/start.sh
    exec /usr/local/bin/su-exec task /golem/resources/start.sh
else
    /bin/chmod +x /golem/resources/start.sh
    /golem/resources/start.sh
fi
