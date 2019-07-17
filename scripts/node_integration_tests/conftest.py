from typing import List
import _pytest
import pytest

from .key_reuse import NodeKeyReuseConfig

DUMP_OUTPUT_ON_CRASH = False
DUMP_OUTPUT_ON_FAIL = False


class DumpOutput:
    @staticmethod
    def enabled_on_crash():
        return DUMP_OUTPUT_ON_CRASH

    @staticmethod
    def enable_on_crash():
        global DUMP_OUTPUT_ON_CRASH
        DUMP_OUTPUT_ON_CRASH = True

    @staticmethod
    def enabled_on_fail():
        return DUMP_OUTPUT_ON_FAIL

    @staticmethod
    def enable_on_fail():
        global DUMP_OUTPUT_ON_FAIL
        DUMP_OUTPUT_ON_FAIL = True


def pytest_addoption(parser: _pytest.config.argparsing.Parser) -> None:

    parser.addoption(
        "--disable-key-reuse", action="store_true",
        help="Disables reuse of provider's and requestor's node keys. "
             "All node_integration_tests run with new, fresh keys."
    )
    parser.addoption(
        "--granary-hostname", action="store",
        help="The ssh hostname for the granary server to use."
    )
    parser.addoption(
        "--dump-output-on-fail", action="store_true",
        help="Dump the nodes' outputs on any test failure."
    )
    parser.addoption(
        "--dump-output-on-crash", action="store_true",
        help="Dump node output of the crashed node on abnormal termination."
    )


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[pytest.Item]) -> None:
    if config.getoption("--disable-key-reuse"):
        NodeKeyReuseConfig.disable()
    hostname = config.getoption("--granary-hostname")
    if hostname:
        NodeKeyReuseConfig.set_granary(hostname)
    if config.getoption('--dump-output-on-crash'):
        DumpOutput.enable_on_crash()
    if config.getoption('--dump-output-on-fail'):
        DumpOutput.enable_on_fail()
