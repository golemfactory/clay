#!/usr/bin/env python
from argparse import ArgumentParser

from golem.config.environments import set_environment

from scripts.node_integration_tests.playbooks import run_playbook
from scripts.node_integration_tests.helpers import mkdatadir


def _add_to_kwargs_reuse_node_keys_parsed_from_string_to_boolean():
    for k, v in vars(args).items():
        if k == 'reuse_node_keys':
            if v == 'True':
                playbook_kwargs.update({'reuse_node_keys': True})
            elif v == 'False':
                playbook_kwargs.update({'reuse_node_keys': False})
            else:
                raise Exception(
                    'Unexpected problem with reuse_node_keys parameter')


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
    parser.add_argument(
        '--reuse_node_keys',
        help="parameter to set if provider and requestor node keys should be "
             "reused. It is done to avoid waiting for GNT and GNTB each time"
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
    _add_to_kwargs_reuse_node_keys_parsed_from_string_to_boolean()

    run_playbook(playbook, **playbook_kwargs)
