#!/usr/bin/env python
from scripts.concent_integration_tests.playbooks import run, rpc_test

run.run_playbook(rpc_test.NoConcentRPCTest)  # type: ignore
