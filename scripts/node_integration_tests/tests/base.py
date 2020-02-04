import contextlib
import os
import pathlib
import subprocess
import unittest
from functools import wraps
from typing import (
    Callable,
    Optional,
    TYPE_CHECKING
)

from scripts.node_integration_tests import conftest
from scripts.node_integration_tests.key_reuse import NodeKeyReuseConfig

from ..helpers import get_testdir
from ..playbook_loader import get_config

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from typing import (
        Dict,
        List,
    )

    from ..playbooks.test_config_base import NodeId


@contextlib.contextmanager
def disabled_key_reuse(reuse_keys: NodeKeyReuseConfig):
    assert reuse_keys is not None, "reuse_keys is not configured"
    was_enabled = reuse_keys.enabled
    reuse_keys.disable()
    try:
        yield None
    finally:
        if was_enabled:
            reuse_keys.enable()


def disable_key_reuse(test_function: Callable) -> Callable:
    @wraps(test_function)
    def wrap(*args, **kwargs) -> None:
        reuse_keys = args[0].reuse_keys
        with disabled_key_reuse(reuse_keys):
            test_function(*args, **kwargs)
    return wrap


class NodeTestBase(unittest.TestCase):
    reuse_keys: Optional[NodeKeyReuseConfig] = None

    @classmethod
    def setUpClass(cls):
        NodeKeyReuseConfig.set_dir(get_testdir())
        cls.reuse_keys = NodeKeyReuseConfig.get()

    @classmethod
    def tearDownClass(cls):
        NodeKeyReuseConfig.reset()

    def setUp(self):
        self.test_dir = get_testdir() / self._relative_id()
        self.nodes = {}
        self.datadirs: 'Dict[NodeId, pathlib.Path]' = {}

    def _relative_id(self):
        # Remove repeated part: `scripts.node_integration_tests.tests.`
        base_folder = __name__[:__name__.rindex('.')+1]
        return self.id().replace(base_folder, '')

    @staticmethod
    def _get_nodes_ids(test_path: str) -> 'List[NodeId]':
        config = get_config(test_path)
        return list(config.nodes.keys())

    def _run_test(self, test_path: str, *args, **kwargs):
        self.nodes = NodeTestBase._get_nodes_ids(test_path)

        self.datadirs = {}
        for node_id in self.nodes:
            datadir = self.test_dir / node_id.value
            self.datadirs[node_id] = datadir
            os.makedirs(datadir)

        cwd = pathlib.Path(__file__).resolve().parent.parent
        test_args = [
            str(cwd / 'run_test.py'),
            test_path,
            *args,
        ]

        for node_id in self.nodes:
            test_args.extend(
                ['--datadir', node_id.value, self.datadirs[node_id]])

        for k, v in kwargs.items():
            test_args.append('--' + k)
            test_args.append(v)

        if conftest.DumpOutput.enabled_on_fail():
            test_args.append('--dump-output-on-fail')

        if conftest.DumpOutput.enabled_on_crash():
            test_args.append('--dump-output-on-crash')

        assert self.reuse_keys is not None, "reuse_keys is not configured"
        on_mainnet = '--mainnet' in args or 'mainnet' in kwargs
        if on_mainnet:
            with disabled_key_reuse(self.reuse_keys):
                self._call_subprocess(test_args)
        else:
            self._call_subprocess(test_args)

    def _call_subprocess(self, test_args):
        self.reuse_keys.begin_test(self.datadirs)
        exit_code = subprocess.call(args=test_args)
        self.reuse_keys.end_test()
        self.assertEqual(exit_code, 0)
