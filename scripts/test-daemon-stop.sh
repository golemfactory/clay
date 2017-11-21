#!/bin/sh
H_FILE=./.test-daemon-hyperg.pid
H_PID=$(cat $H_FILE)
rm $H_FILE || echo "Error, not able to delete '$H_FILE'" 

kill $H_PID || echo "Error, not able to stop hyperg"


I_FILE=./.test-daemon-ipfs.pid
I_PID=$(cat $I_FILE)
rm $I_FILE || echo "Error, not able to delete '$I_FILE'" 

kill $I_PID || echo "Error, not able to stop ipfs"


exit 0
