#!/usr/bin/env python
from argparse import ArgumentParser

from golem.config.environments import set_environment

from scripts.node_integration_tests.playbooks import run_playbook
from scripts.node_integration_tests.helpers import mkdatadir

if __name__ == '__main__':

    parser = ArgumentParser(description="Runs a single test playbook.")
    parser.add_argument(
        'playbook_class',
        help="a dot-separated path to the playbook class within `playbooks`,"
             " e.g. golem.regular_run.RegularRun",
    )
    parser.add_argument(
        '--task-package',
        default='test_task_1',
        help='a directory within `tasks` containing the task package'
    )
    parser.add_argument(
        '--task-settings',
        required=False,
        help='the task settings set to use, see `tasks.__init__.py`'
    )
    parser.add_argument(
        '--provider-datadir',
        default=mkdatadir('provider'),
        help="the provider node's datadir",
    )
    parser.add_argument(
        '--requestor-datadir',
        default=mkdatadir('requestor'),
        help="the requestor node's datadir",
    )
    parser.add_argument(
        '--dump-output-on-fail',
        action='store_true',
        required=False,
        help="dump the nodes' outputs on test fail",
    )
    parser.add_argument(
        '--mainnet',
        action='store_true',
        required=False,
        help="use the mainnet environment to run the test "
             "(the playbook must also use mainnet)",
    )
    args = parser.parse_args()

    if args.mainnet:
        set_environment('mainnet', 'disabled')

    playbook_class_path = args.playbook_class
    playbook_module_path, _, playbook_class_name = \
        playbook_class_path.rpartition('.')
    playbook_path, _, playbook_module_name = \
        playbook_module_path.rpartition('.')
    playbooks_path = 'scripts.node_integration_tests.playbooks'

    if playbook_path:
        playbooks_path += '.' + playbook_path

    try:
        playbook_module = getattr(
            __import__(
                playbooks_path,
                fromlist=[playbook_module_name]
            ), playbook_module_name
        )

        playbook = getattr(playbook_module, playbook_class_name)
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "The provided playbook `%s` couldn't be located in `playbooks` " %
            args.playbook_class
        ) from e

    playbook_kwargs = {
        k: v
        for k, v in vars(args).items()
        if k in [
            'task_package',
            'task_settings',
            'provider_datadir',
            'requestor_datadir',
            'dump_output_on_fail',
        ]
           and v
    }

    run_playbook(playbook, **playbook_kwargs)
