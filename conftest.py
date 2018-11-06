from typing import List
import pytest
import _pytest


def pytest_addoption(parser: _pytest.config.Parser) -> None:
    parser.addoption("--runslow", action="store_true",
                     default=False, help="run slow tests")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[_pytest.main.Item]) -> None:
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
