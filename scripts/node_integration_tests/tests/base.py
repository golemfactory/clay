import os
import pathlib
import shutil
import subprocess
from functools import wraps
from typing import Callable

from scripts.node_integration_tests import conftest

from ..helpers import get_testdir

KEYSTORE_DIR = 'rinkeby/keys'


def disable_key_reuse(test_function: Callable)-> Callable:
    @wraps(test_function)
    def wrap(*args, **kwargs) -> None:
        args[0].reuse_keys = False
        test_function(*args, **kwargs)
    return wrap


class NodeTestBase:
    def setUp(self):
        test_dir = pathlib.Path(get_testdir()) / self._relative_id()
        self.provider_datadir = test_dir / 'provider'
        self.requestor_datadir = test_dir / 'requestor'
        os.makedirs(self.provider_datadir)
        os.makedirs(self.requestor_datadir)
        self.reuse_keys = True

        self.key_reuse_dir = test_dir.parent / 'key_reuse'
        self.provider_reuse_dir = self.key_reuse_dir / 'provider'
        self.requestor_reuse_dir = self.key_reuse_dir / 'requestor'

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

    def _run_test(self, playbook_class_path: str, *args, **kwargs):
        cwd = pathlib.Path(os.path.realpath(__file__)).parent.parent
        test_args = [
            str(cwd / 'run_test.py'),
            playbook_class_path,
            *args,
            '--provider-datadir', self.provider_datadir,
            '--requestor-datadir', self.requestor_datadir,
        ]
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
        self._replace_keystore(
            self.provider_reuse_dir, self.provider_datadir
        )
        self._replace_keystore(
            self.requestor_reuse_dir, self.requestor_datadir
        )

    def _copy_keystores(self):
        self._prepare_keystore_reuse_folders()
        self._copy_keystore(
            self.provider_datadir, self.provider_reuse_dir
        )
        self._copy_keystore(
            self.requestor_datadir, self.requestor_reuse_dir
        )

    def _prepare_keystore_reuse_folders(self) -> None:
        shutil.rmtree(self.provider_reuse_dir, ignore_errors=True)
        shutil.rmtree(self.requestor_reuse_dir, ignore_errors=True)
        try:
            os.makedirs(self.provider_reuse_dir)
            os.makedirs(self.requestor_reuse_dir)
        except OSError:
            print('Unexpected problem with creating folders for keystore')
            raise

    @staticmethod
    def _copy_keystore(datadir: pathlib.Path, reuse_dir: pathlib.Path) -> None:
        src = str(datadir / KEYSTORE_DIR / 'keystore.json')
        dst = str(reuse_dir / 'keystore.json')
        shutil.copyfile(src, dst)
