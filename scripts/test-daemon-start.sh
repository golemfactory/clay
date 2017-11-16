#!/bin/sh

echo "Starting hyperg"
hyperg > /dev/null 2>&1 &
H_PID=$!

echo $H_PID > ./.test-daemon-hyperg.pid

echo "Starting ipfs"
ipfs config --json Bootstrap "[]"
ipfs config --json SupernodeRouting.Servers "[]"
ipfs config --json Addresses.Swarm '["/ip6/::/tcp/4001", "/ip6/::/udp/4002/utp", "/ip4/0.0.0.0/udp/4002/utp"]'
ipfs daemon > /dev/null 2>&1 &
I_PID=$!

echo $I_PID > ./.test-daemon-ipfs.pid

exit 0
