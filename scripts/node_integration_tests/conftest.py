from typing import List
import _pytest

REUSE_KEYS = True


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

    def disable(self):
        global REUSE_KEYS
        REUSE_KEYS = False

    @property
    def enabled(self):
        return REUSE_KEYS


def pytest_addoption(parser: _pytest.config.Parser) -> None:

    parser.addoption(
        "--disable-key-reuse", action="store_true",
        help="Parameter disables reusing of provider's and "
             "requestor's node keys. All node_integration_tests "
             "run with new, fresh keys."
    )


def pytest_collection_modifyitems(config: _pytest.config.Config,
                                  items: List[_pytest.main.Item]) -> None:
    if config.getoption("--disable-key-reuse"):
        NodeKeyReuse().disable()
