from typing import List
import pytest
import _pytest

DISABLE_KEY_REUSE_COMMAND_LINE = False


def pytest_addoption(parser: _pytest.config.Parser) -> None:
    parser.addoption("--runslow", action="store_true",
                     default=False, help="run slow tests")

    parser.addoption("--disable-key-reuse",
                     help="Parameter disables reusing of provider's and "
                          "requestor's node keys. All node_integration_tests"
                          "run with new, fresh keys ")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[_pytest.main.Item]) -> None:
    if config.getoption("--disable-key-reuse") and \
            config.getvalue("--disable-key-reuse") == 'yes':
        global DISABLE_KEY_REUSE_COMMAND_LINE
        DISABLE_KEY_REUSE_COMMAND_LINE = True

    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
