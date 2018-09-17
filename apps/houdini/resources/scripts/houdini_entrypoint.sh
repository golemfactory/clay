#!/bin/bash

/etc/init.d/sesinetd start
/usr/local/bin/entrypoint.sh $@
