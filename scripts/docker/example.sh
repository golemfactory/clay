#!/bin/bash

set -e

if [ "$#" -lt 2 ]; then
    echo "$0 [image_name] [source_path]"
    exit 1
fi

NODE_COUNT=3
DOCKER_BRIDGE="docker0"
DOCKER_ADDR=$(ifconfig ${DOCKER_BRIDGE} | grep "inet addr" | cut -d':' -f2 | cut -d' ' -f1 | sed "s/\n|\\n//g")

CMD="python docker_helper.py $1"
IPFS_PATH="/usr/local/bin/ipfs"
GOLEM_DIR=$2

echo "   [i] Killing + starting containers"
${CMD} kill %{container}
${CMD} rm %{container}

for i in $(seq 1 $NODE_COUNT); do
    docker run -d $1 --entrypoint=/bin/bash
done

echo "   [i] Initializing IPFS"

${CMD} cp ${IPFS_PATH} %{container}:/usr/local/bin/ipfs
${CMD} exec %{container} /usr/local/bin/ipfs init -f

echo "   [i] Starting the IFPS daemon"

${CMD} exec %{container} sh -c "echo 'nohup /usr/local/bin/ipfs daemon >/tmp/ipfs-daemon.log &' > /root/ipfs-daemon.sh"
${CMD} exec -d %{container} sh /root/ipfs-daemon.sh
${CMD} exec %{container} sh -c "while ! grep 'Daemon is ready' /tmp/ipfs-daemon.log; do sleep 0.5; done;"

echo "   [i] Replacing golem"
${CMD} exec %{container} sh -c "rm -rf /opt/golem"
${CMD} cp ${GOLEM_DIR} %{container}:/opt/golem

echo "   [i] Clearing resources"
${CMD} exec %{container} sh -c "rm -rf /opt/golem/gnr/benchmarks"

# echo "   [i] Setting up golem"
# ${CMD} exec %{container} sh -c "cd /opt/golem && python setup.py clean > /tmp/golem-setup.log"
# ${CMD} exec %{container} sh -c "cd /opt/golem && python setup.py develop >> /tmp/golem-setup.log"

echo "   [i] Executing GNR node"
${CMD} exec %{container} sh -c "rm -rf /root/.local/golem/keys"
${CMD} exec %{container} sh -c "echo 'cd /opt/golem && nohup python gui/node.py -a %{ip} -p ${DOCKER_ADDR}:40102 >/tmp/gnr-node.log 2>&1 &' > /root/gnr-node.sh"
${CMD} exec -d %{container} sh /root/gnr-node.sh
