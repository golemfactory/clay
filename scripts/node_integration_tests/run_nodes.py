#!/usr/bin/env python
from aenum import extend_enum
import argparse
import time
import typing

from scripts.node_integration_tests import helpers
from scripts.node_integration_tests.run_test import DictAction
from scripts.node_integration_tests.playbooks.test_config_base import \
    NodeId, make_node_config_from_env

if typing.TYPE_CHECKING:
    from scripts.node_integration_tests.playbooks.test_config_base import \
        NodeConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a pair of golem nodes with default test parameters"
    )
    parser.add_argument(
        '--datadir',
        nargs=2,
        action=DictAction,
        metavar=('NODE', 'PATH'),
        help="override datadir path for given node"
    )
    parser.add_argument(
        'nodes',
        nargs='*',
        default=[NodeId.requestor.value, NodeId.provider.value],
    )
    return parser.parse_args()


def make_node_configs(node_names: typing.Iterable[str],
                      override_datadirs: typing.Dict[str, str]) \
        -> typing.Dict[NodeId, 'NodeConfig']:
    node_configs: typing.Dict[NodeId, 'NodeConfig'] = {
        NodeId(node_name): make_node_config_from_env(node_name, i)
        for i, node_name in enumerate(node_names)
    }

    for node_name, datadir in override_datadirs.items():
        node_id = NodeId(node_name)
        if node_id not in node_configs:
            raise Exception("can't override datadir for undefined node"
                            f" '{node_name}'")
        node_configs[node_id].datadir = datadir

    return node_configs


def main():
    args = parse_args()

    for node_name in args.nodes:
        if node_name in [NodeId.requestor.value, NodeId.provider.value]:
            continue
        extend_enum(NodeId, node_name, node_name)

    node_configs = make_node_configs(args.nodes, args.datadir)

    nodes = {
        node_id: helpers.run_golem_node(node_config.script,
                                        node_config.make_args())
        for node_id, node_config in node_configs.items()
    }

    queues = {
        node_id: helpers.get_output_queue(node)
        for node_id, node in nodes.items()
    }

    try:
        while True:
            time.sleep(1)
            for node_id, queue in queues.items():
                helpers.print_output(queue, node_id.value + ' ')

            exit_codes = {
                node_id: node.poll()
                for node_id, node in nodes.items()
            }

            for node_id, exit_code in exit_codes.items():
                helpers.report_termination(exit_code, node_id.value)

            if all(exit_code is not None for exit_code in exit_codes.values()):
                break

    except KeyboardInterrupt:
        for node_id, node in nodes.items():
            helpers.gracefully_shutdown(node, node_id.value)


if __name__ == '__main__':
    main()
