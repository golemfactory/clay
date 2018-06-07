#!/usr/bin/env python
import sys

from scripts.concent_node_tests.tests.base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'regular_provider'
    requestor_node_script = 'requestor_no_ack_rct'


playbook = RegularRun.start()
print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
