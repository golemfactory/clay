#!/usr/bin/env python
import sys

from twisted.internet import reactor

from scripts.concent_node_tests.tests.base import NodeTestPlaybook


class RegularRun(NodeTestPlaybook):
    provider_node_script = 'regular_provider'
    requestor_node_script = 'regular_requestor'


playbook = RegularRun.start()
print("exit code", playbook.exit_code)
sys.exit(playbook.exit_code)
