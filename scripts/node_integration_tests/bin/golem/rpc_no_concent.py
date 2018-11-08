#!/usr/bin/env python
from scripts.node_integration_tests.playbooks import run, rpc_test

run.run_playbook(rpc_test.NoConcentRPCTest)  # type: ignore
