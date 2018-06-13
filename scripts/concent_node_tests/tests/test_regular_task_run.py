#!/usr/bin/env python
import sys

from scripts.concent_node_tests.tests.base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/regular'
    requestor_node_script = 'requestor/regular'


playbook = RegularRun.start()
if playbook.exit_code:
    print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
