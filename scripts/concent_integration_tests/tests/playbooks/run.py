import sys

from scripts.concent_integration_tests.tests.playbooks.base import (
    NodeTestPlaybook
)


def run_playbook(playbook_cls: NodeTestPlaybook, **kwargs):
    playbook = playbook_cls.start(**kwargs)

    if playbook.exit_code:
        print("exit code", playbook.exit_code)

    sys.exit(playbook.exit_code)
