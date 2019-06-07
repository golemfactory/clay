import os
from pathlib import Path
import subprocess
import unittest
from functools import wraps
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    TYPE_CHECKING
)

from scripts.node_integration_tests import conftest
from scripts.node_integration_tests.key_reuse import NodeKeyReuse

from ..helpers import get_testdir
from ..playbook_loader import get_config

if TYPE_CHECKING:
    from ..playbooks.test_config_base import NodeId


def disable_key_reuse(test_function: Callable) -> Callable:
    @wraps(test_function)
    def wrap(*args, **kwargs) -> None:
        reuse_keys = args[0].reuse_keys
        was_enabled = reuse_keys.enabled
        reuse_keys.disable()
        test_function(*args, **kwargs)
        if was_enabled:
            reuse_keys.enable()
    return wrap


class NodeTestBase(unittest.TestCase):
    reuse_keys: Optional[NodeKeyReuse] = None

    @classmethod
    def setUpClass(cls):
        cls.reuse_keys = NodeKeyReuse.get(get_testdir())

    @classmethod
    def tearDownClass(cls):
        NodeKeyReuse.reset()

    def setUp(self):
        self.test_dir = get_testdir() / self._relative_id()

    def _relative_id(self):
        return self.id().replace(__name__ + '.', '')

    @staticmethod
    def _get_nodes_ids(test_path: str) -> 'List[NodeId]':
        config = get_config(test_path)
        return list(config.nodes.keys())

    def _run_test(self, test_path: str, *args, **kwargs):
        self.nodes = NodeTestBase._get_nodes_ids(test_path)

        self.datadirs: 'Dict[NodeId, pathlib.Path]' = {}
        for node_id in self.nodes:
            datadir = self.test_dir / node_id.value
            self.datadirs[node_id] = datadir
            os.makedirs(datadir)

        cwd = Path(__file__).resolve().parent.parent
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
        self.reuse_keys.begin_test(self.datadirs)
        exit_code = subprocess.call(args=test_args)
        self.reuse_keys.end_test()
        self.assertEqual(exit_code, 0)
