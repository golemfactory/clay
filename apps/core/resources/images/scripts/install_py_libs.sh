#!/bin/sh

 apt-get update \
 &&  apt-get install -y python3-pip \
 &&  pip3 install --upgrade pip \
 &&  cd /usr/local/lib/python3.6/dist-packages \
 && for LIB in $@
        do
            if [ "$1" -eq "$LIB" ] 2>/dev/null
            then
                continue
            elif [ "$1" -eq 0 ]
            then
                pip install $LIB
            else
                pip install -r $LIB
            fi
        done \
&& apt-get remove -y python3-pip \
&& apt-get clean \
&& apt-get -y autoremove \
&& rm -rf /var/lib/apt/lists/* \
&& rm -rf /usr/local/lib/python3.6/dist-packages/pip* \
&& rm /usr/local/bin/pip*