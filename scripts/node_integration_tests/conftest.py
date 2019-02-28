from typing import List
import _pytest

DISABLE_KEY_REUSE_COMMAND_LINE = False


def pytest_addoption(parser: _pytest.config.Parser) -> None:

    parser.addoption("--disable-key-reuse", action="store_true",
                     help="Parameter disables reusing of provider's and "
                          "requestor's node keys. All node_integration_tests"
                          "run with new, fresh keys ")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[_pytest.main.Item]) -> None:
    if config.getoption("--disable-key-reuse") is True:
        global DISABLE_KEY_REUSE_COMMAND_LINE
        DISABLE_KEY_REUSE_COMMAND_LINE = True
