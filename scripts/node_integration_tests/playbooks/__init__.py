import sys
from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import NodeTestPlaybook
    from .test_config_base import TestConfigBase


def run_playbook(playbook_cls: 'Type[NodeTestPlaybook]',
                 config: 'TestConfigBase') -> None:
    playbook = playbook_cls.start(config)

    if playbook.exit_code:
        print("exit code", playbook.exit_code)

    sys.exit(playbook.exit_code)
