import sys
from argparse import ArgumentParser

from .base import NodeTestPlaybook


def run_playbook(playbook_cls: NodeTestPlaybook, **kwargs):
    parser = ArgumentParser(description=playbook_cls.playbook_description)
    parser.add_argument(
        '--task-package',
        default='test_task_1',
        help='a directory within `tasks` containing the task package'
    )
    parser.add_argument(
        '--task-settings',
        default=None,
        help='the task settings set to use, see `tasks.__init__.py`'
    )
    args = parser.parse_args()

    kwargs.update({'task_package': args.task_package})
    if args.task_settings:
        kwargs.update({'task_settings': args.task_settings})

    playbook = playbook_cls.start(**kwargs)

    if playbook.exit_code:
        print("exit code", playbook.exit_code)

    sys.exit(playbook.exit_code)
