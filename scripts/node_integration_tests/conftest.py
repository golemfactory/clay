from typing import List
import _pytest

from scripts.node_integration_tests.tests.base import \
    disable_reuse_keys_command_line


def pytest_addoption(parser: _pytest.config.Parser) -> None:

    parser.addoption("--disable-key-reuse", action="store_true",
                     help="Parameter disables reusing of provider's and "
                          "requestor's node keys. All node_integration_tests"
                          "run with new, fresh keys ")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  _items: List[_pytest.main.Item]) -> None:
    if config.getoption("--disable-key-reuse") is True:
        disable_reuse_keys_command_line()
