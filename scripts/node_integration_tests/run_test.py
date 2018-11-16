#!/usr/bin/env python
import sys
from scripts.node_integration_tests.playbooks import run_playbook
from golem.config.environments import set_environment

if __name__ == '__main__':
    if '--mainnet' in sys.argv:
        set_environment('mainnet', 'disabled')
        sys.argv.pop(sys.argv.index('--mainnet'))

    playbook_class_path = sys.argv.pop(1)
    playbook_module_path, _, playbook_class_name = \
        playbook_class_path.rpartition('.')
    playbook_path, _, playbook_module_name = \
        playbook_module_path.rpartition('.')
    playbooks_path = 'scripts.node_integration_tests.playbooks'

    if playbook_path:
        playbooks_path += '.' + playbook_path

    playbook_module = getattr(
        __import__(
            playbooks_path,
            fromlist=[playbook_module_name]
        ), playbook_module_name
    )

    playbook = getattr(playbook_module, playbook_class_name)

    run_playbook(playbook)
