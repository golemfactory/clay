#!/usr/bin/env python
import argparse
from typing import TYPE_CHECKING

from golem.core import variables

from scripts.node_integration_tests.playbook_loader import \
    get_config_and_playbook_class
from scripts.node_integration_tests.playbooks import run_playbook
from scripts.node_integration_tests.playbooks.test_config_base import (
    NodeId,
)


if TYPE_CHECKING:
    # pylint: disable=unused-import
    from scripts.node_integration_tests.playbooks.test_config_base \
        import TestConfigBase


class DictAction(argparse.Action):
    """
    This action must be used by arguments with nargs=2.
    It collects arguments where first argument is a key in a dictionary and
    second is value.
    If a key is repeated, the value of last occurence is used.

    Example:
    parser = argparse.ArgumentParser()
    parser.add_argument('--foo', nargs=2, action=DictAction)
    args = parser.parse_args([
        '--foo', 'a', '1',
        '--foo', 'b', '2',
        '--foo', 'a', '3',
    ])
    assert args.foo == {
        'a': '3',
        'b': '2',
    }
    """

    def __call__(self, parser, namespace, values, option_string=None) -> None:
        assert self.nargs == 2
        dest = getattr(namespace, self.dest)
        if dest is None:
            setattr(namespace, self.dest, {values[0]: values[1]})
        else:
            dest[values[0]] = values[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runs a single test playbook.")
    parser.add_argument(
        'test_path',
        help="a dot-separated path to the test module within `playbooks`,"
             " e.g. golem.regular_run",
    )
    parser.add_argument(
        '--task-package',
        help='a directory within `tasks` containing the task package'
    )
    parser.add_argument(
        '--task-settings',
        help='the task settings set to use, see `tasks.__init__.py`'
    )
    parser.add_argument(
        '--datadir',
        nargs=2,
        action=DictAction,
        metavar=('NODE', 'PATH'),
        help=("override datadir path for given node. standard node names are"
              f" '{NodeId.requestor.value}' and '{NodeId.provider.value}'")
    )
    parser.add_argument(
        '--dump-output-on-fail',
        action='store_true',
        help="dump the nodes' outputs on test fail",
    )
    parser.add_argument(
        '--dump-output-on-crash',
        action='store_true',
        help="dump node output of the crashed node on abnormal termination",
    )
    parser.add_argument(
        '--mainnet',
        action='store_true',
        help="use the mainnet environment to run the test "
             "(the playbook must also use mainnet)",
    )
    parser.add_argument(
        '--concent',
        choices=variables.CONCENT_CHOICES,
        default='staging',
        help="choose concent option",
    )
    return parser.parse_args()


def override_config(config: 'TestConfigBase', args: argparse.Namespace) -> None:
    for k, v in vars(args).items():
        if v is None:
            continue

        if k in [
                'task_package',
                'task_settings',
                'dump_output_on_fail',
                'dump_output_on_crash',
        ]:
            setattr(config, k, v)
        elif k in [
                'concent',
                'mainnet',
        ]:
            for node_config in config.nodes.values():
                setattr(node_config, k, v)
        elif k == 'datadir':
            for node_name, datadir in v.items():
                node_id = NodeId(node_name)
                if node_id not in config.nodes:
                    raise Exception("can't override datadir for undefined node"
                                    f" '{node_name}'")
                node_configs = config.nodes[node_id]
                if isinstance(node_configs, list):
                    for node_config in node_configs:
                        node_config.datadir = datadir
                else:
                    node_configs.datadir = datadir

    config.update_task_dict()


def main():
    args = parse_args()

    config, playbook_class = get_config_and_playbook_class(args.test_path)

    override_config(config, args)

    run_playbook(playbook_class, config)


if __name__ == '__main__':
    main()
