#!/bin/sh
H_FILE=./.test-daemon-hyperg.pid
H_PID=$(cat $H_FILE)
rm $H_FILE || echo "Error, not able to delete '$H_FILE'"

kill $H_PID || echo "Error, not able to stop hyperg"


exit 0
