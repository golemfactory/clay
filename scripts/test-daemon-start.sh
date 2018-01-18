#!/bin/bash

let DEBUG=1
H_FILE=./.test-daemon-hyperg.pid
[ -e $H_FILE ] && H_PID=$(cat $H_FILE)

find_and_kill_pid () {
  [ $DEBUG -eq 1 ] && echo "Checking for pid $H_PID" >&2
  if ps -p $H_PID > /dev/null; then
    [ $DEBUG -eq 1 ] && echo "Killing pid $H_PID" >&2
    kill -9 $H_PID
    let res=$?
    [ $res -eq 1 ] && echo "Unable to kill pid $H_PID" >&2 && exit 1
  fi
}

kill_running_hyperg () {
  RUNNING_PID=`pgrep hyperg`
  let res=$?
  [ $res -eq 1 ] && exit 0
  kill -9 $RUNNING_PID
  let res=$?
  [ $res -eq 1 ] && echo "Unable to kill pid $RUNNING_PID" >&2 && exit 1
}

[ -e $H_FILE ] && find_and_kill_pid

kill_running_hyperg

echo "Starting hyperg"
hyperg > /dev/null 2>&1 &
H_PID=$!

echo $H_PID > $H_FILE

exit 0
