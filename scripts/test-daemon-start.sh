#!/bin/sh

echo "Starting hyperg"
hyperg > /dev/null 2>&1 &
H_PID=$!

echo $H_PID > ./.test-daemon-hyperg.pid

exit 0
