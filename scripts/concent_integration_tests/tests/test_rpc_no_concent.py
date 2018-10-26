#!/usr/bin/env python
from scripts.concent_integration_tests.tests.playbooks import rpc_test, run

run.run_playbook(rpc_test.NoConcentRPCTest)  # type: ignore
