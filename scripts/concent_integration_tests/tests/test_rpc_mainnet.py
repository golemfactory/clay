#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import rpc_test, run
from golem.config.environments import set_environment

set_environment('mainnet', 'disabled')

run.run_playbook(rpc_test.MainnetRPCTest)  # type: ignore
