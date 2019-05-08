import os
import pathlib
import shutil
import subprocess
from functools import wraps
from typing import (
    Callable,
    Dict,
    List,
    TYPE_CHECKING
)

from scripts.node_integration_tests import conftest

from ..helpers import get_testdir
from ..playbook_loader import get_config

if TYPE_CHECKING:
    from ..playbooks.test_config_base import NodeId


KEYSTORE_DIR = 'rinkeby/keys'


def disable_key_reuse(test_function: Callable)-> Callable:
    @wraps(test_function)
    def wrap(*args, **kwargs) -> None:
        args[0].reuse_keys = False
        test_function(*args, **kwargs)
    return wrap


class NodeTestBase:
    def setUp(self):
        self.test_dir = pathlib.Path(get_testdir()) / self._relative_id()
        self.reuse_keys = True
        self.key_reuse_dir = self.test_dir.parent / 'key_reuse'

    def tearDown(self):
        key_reuse = conftest.NodeKeyReuse.get()
        if key_reuse.enabled and not key_reuse.keys_ready:
            try:
                self._copy_keystores()
            except FileNotFoundError:
                print('Copying keystores failed...')
                return

            key_reuse.mark_keys_ready()

    def _relative_id(self):
        from . import __name__ as parent_name
        return self.id().replace(parent_name + '.', '')

    def _can_recycle_keys(self) -> bool:
        return all([conftest.NodeKeyReuse.get().keys_ready, self.reuse_keys])

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

        cwd = pathlib.Path(os.path.realpath(__file__)).parent.parent
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

        if self._can_recycle_keys():
            self._recycle_keys()

        return subprocess.call(args=test_args)

    @staticmethod
    def _replace_keystore(src: pathlib.Path, dst: pathlib.Path) -> None:
        src_file = src / 'keystore.json'
        dst_file = dst / KEYSTORE_DIR / 'keystore.json'
        os.makedirs(str(dst / KEYSTORE_DIR))
        shutil.copyfile(str(src_file), str(dst_file))

    def _recycle_keys(self):
        # this is run before running second and later tests
        for i, node_id in enumerate(self.nodes):
            reuse_dir = self.key_reuse_dir / str(i)
            if not reuse_dir.exists():
                continue
            NodeTestBase._replace_keystore(
                reuse_dir, self.datadirs[node_id])

    def _copy_keystores(self):
        # this is run after tests
        self._prepare_keystore_reuse_folders()
        for i, node_id in enumerate(self.nodes):
            NodeTestBase._copy_keystore(
                self.datadirs[node_id], self.key_reuse_dir / str(i))

    def _prepare_keystore_reuse_folders(self) -> None:
        # this is run after tests
        try:
            for i in range(len(self.nodes)):
                reuse_dir = self.key_reuse_dir / str(i)
                shutil.rmtree(reuse_dir, ignore_errors=True)
                os.makedirs(reuse_dir)
        except OSError:
            print('Unexpected problem with creating folders for keystore')
            raise

    @staticmethod
    def _copy_keystore(datadir: pathlib.Path, reuse_dir: pathlib.Path) -> None:
        src = str(datadir / KEYSTORE_DIR / 'keystore.json')
        dst = str(reuse_dir / 'keystore.json')
        shutil.copyfile(src, dst)
