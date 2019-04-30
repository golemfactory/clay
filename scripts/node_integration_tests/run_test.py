#!/usr/bin/env python
import argparse
from importlib import import_module
from typing import (
    List,
    TYPE_CHECKING,
    Tuple,
    Type,
    Union,
)

from golem.config.environments import set_environment

from scripts.node_integration_tests.playbooks import run_playbook
from scripts.node_integration_tests.playbooks.base import NodeTestPlaybook

if TYPE_CHECKING:
    from scripts.node_integration_tests.playbooks.test_config_base \
        import NodeConfig, TestConfigBase


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runs a single test playbook.")
    parser.add_argument(
        'test_path',
        help="a dot-separated path to the test moduse within `playbooks`,"
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
        '--provider-datadir',
        help="the provider node's datadir",
    )
    parser.add_argument(
        '--requestor-datadir',
        help="the requestor node's datadir",
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
    return parser.parse_args()


def get_config_and_playbook_class(test_path: str) \
        -> 'Tuple[TestConfigBase, Type[NodeTestPlaybook]]':
    PLAYBOOKS_PATH = 'scripts.node_integration_tests.playbooks'
    TEST_CONFIG_MODULE_NAME = "test_config"
    PLAYBOOK_MODULE_NAME = "playbook"
    CONFIG_CLASS_NAME = "TestConfig"
    PLAYBOOK_CLASS_NAME = "Playbook"

    try:
        # simple test, only with config
        config_module = import_module(f"{PLAYBOOKS_PATH}.{test_path}")
        if hasattr(config_module, CONFIG_CLASS_NAME):
            return getattr(config_module, CONFIG_CLASS_NAME)(), NodeTestPlaybook

        # complicated test, with config and custom playbook
        config_module = import_module(
            f"{PLAYBOOKS_PATH}.{test_path}.{TEST_CONFIG_MODULE_NAME}")
        playbook_module = import_module(
            f"{PLAYBOOKS_PATH}.{test_path}.{PLAYBOOK_MODULE_NAME}")
        return (getattr(config_module, CONFIG_CLASS_NAME)(),
                getattr(playbook_module, PLAYBOOK_CLASS_NAME))
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"The provided playbook `{test_path}` "
            "couldn't be located in `playbooks`"
        ) from e


def override_datadir(
        role_name: str,
        node_configs: 'Union[None, NodeConfig, List[NodeConfig]]',
        datadir: str) -> None:
    if node_configs is None:
        raise Exception(f"can't override datadir for {role_name},"
                        " because it's disabled")
    if isinstance(node_configs, list):
        for node_config in node_configs:
            node_config.datadir = datadir
    else:
        node_configs.datadir = datadir


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
        elif k == 'provider_datadir':
            override_datadir('provider', config.provider, v)
        elif k == 'requestor_datadir':
            override_datadir('requestor', config.requestor, v)


def main():
    args = parse_args()

    if args.mainnet:
        set_environment('mainnet', 'disabled')

    config, playbook_class = get_config_and_playbook_class(args.test_path)

    override_config(config, args)

    run_playbook(playbook_class, config)


if __name__ == '__main__':
    main()
