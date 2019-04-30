from typing import List
import _pytest

REUSE_KEYS = True
DUMP_OUTPUT_ON_CRASH = False
DUMP_OUTPUT_ON_FAIL = False


class NodeKeyReuseException(Exception):
    pass


class NodeKeyReuse:
    instance = None
    _first_test = True

    @classmethod
    def get(cls):
        if not cls.instance:
            cls.instance = cls()
        return cls.instance

    @property
    def keys_ready(self):
        return not self._first_test

    def mark_keys_ready(self):
        if not self.enabled:
            raise NodeKeyReuseException("Key reuse disabled.")
        self._first_test = False

    @staticmethod
    def disable():
        global REUSE_KEYS
        REUSE_KEYS = False

    @property
    def enabled(self):
        return REUSE_KEYS


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


def pytest_addoption(parser: _pytest.config.Parser) -> None:

    parser.addoption(
        "--disable-key-reuse", action="store_true",
        help="Disables reuse of provider's and requestor's node keys. "
             "All node_integration_tests run with new, fresh keys."
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
                                  items: List[_pytest.main.Item]) -> None:
    if config.getoption("--disable-key-reuse"):
        NodeKeyReuse.disable()
    if config.getoption('--dump-output-on-crash'):
        DumpOutput.enable_on_crash()
    if config.getoption('--dump-output-on-fail'):
        DumpOutput.enable_on_fail()
