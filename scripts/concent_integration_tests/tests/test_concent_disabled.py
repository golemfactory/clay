#!/usr/bin/env python
import sys

from scripts.concent_integration_tests.tests.base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'provider/no_concent'
    requestor_node_script = 'requestor/no_concent'


playbook = RegularRun.start()
if playbook.exit_code:
    print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
