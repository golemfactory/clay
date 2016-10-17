#!/bin/bash

EXEC_DIR=$(readlink -f $(find . -name "exe.*" -type d -print -quit))
EXEC_NAME="golemcli"

"$EXEC_DIR/$EXEC_NAME" $@
