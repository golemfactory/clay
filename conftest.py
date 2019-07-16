from typing import List
import _pytest
import pytest


def pytest_addoption(parser: _pytest.config.argparsing.Parser) -> None:
    parser.addoption("--runslow", action="store_true",
                     default=False, help="run slow tests")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[pytest.Item]) -> None:
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
