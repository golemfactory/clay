from typing import List
import pytest
import _pytest


def pytest_addoption(parser: _pytest.config.Parser) -> None:
    parser.addoption("--runslow", action="store_true",
                     default=False, help="run slow tests")
    parser.addoption("--runfirejail", action="store_true",
                     default=False, help="run firejail tests")


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[_pytest.main.Item]) -> None:
    if not config.getoption("--runfirejail"):
        skip_firejail = pytest.mark.skip(
            reason="need --runfirejail option to run")
        for item in items:
            if "firejail" in item.keywords:
                item.add_marker(skip_firejail)
    if not config.getoption("--runslow"):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
