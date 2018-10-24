#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import mainnet_rpc, run


run.run_playbook(mainnet_rpc.MainnetRPCTest)  # type: ignore
