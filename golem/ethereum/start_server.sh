#!/bin/sh

geth --datadir ~/.local/share/golem/ethereum9/server --networkid 9 --genesis `dirname $0`/genesis_golem.json  --port 30900  --nodekeyhex 476f6c656d204661756365742020202020202020202020202020202020202020 --gasprice 0 --etherbase cfdc7367e9ece2588afe4f530a9adaa69d5eaedb js `dirname $0`/mine_pending_transactions.js
