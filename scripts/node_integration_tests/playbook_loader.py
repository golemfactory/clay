from importlib import import_module
from typing import (
    Tuple,
    Type,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .playbooks.base import NodeTestPlaybook
    from .playbooks.test_config_base import TestConfigBase


PLAYBOOKS_PATH = 'scripts.node_integration_tests.playbooks'
TEST_CONFIG_MODULE_NAME = "test_config"
PLAYBOOK_MODULE_NAME = "playbook"
CONFIG_CLASS_NAME = "TestConfig"
PLAYBOOK_CLASS_NAME = "Playbook"


def get_config(test_path: str) -> 'TestConfigBase':
    try:
        # simple test, only with config
        config_module = import_module(f"{PLAYBOOKS_PATH}.{test_path}")
        if hasattr(config_module, CONFIG_CLASS_NAME):
            return getattr(config_module, CONFIG_CLASS_NAME)()

        # complicated test, with config and custom playbook
        config_module = import_module(
            f"{PLAYBOOKS_PATH}.{test_path}.{TEST_CONFIG_MODULE_NAME}")
        return getattr(config_module, CONFIG_CLASS_NAME)()
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"The provided playbook `{test_path}` "
            "couldn't be located in `playbooks`"
        ) from e


def get_config_and_playbook_class(test_path: str) \
        -> 'Tuple[TestConfigBase, Type[NodeTestPlaybook]]':

    # It is important that it's not loaded at top level.
    from scripts.node_integration_tests.playbooks.base import NodeTestPlaybook

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
