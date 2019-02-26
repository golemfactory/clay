import os
import pathlib
import shutil
import subprocess
import time
from functools import wraps
from shutil import copyfile
from threading import Thread
from typing import Callable

from ..helpers import get_testdir


def disable_key_reuse(test_function: Callable)-> Callable:
    @wraps(test_function)
    def wrap(*args, **kwargs) -> None:
        args[0].disable_keys_decorator = True
        test_function(*args, **kwargs)
    return wrap


class ReuseNodeKeys:
    instance = None

    class __ReuseNodeKeys:
        first_test_in_set = True

        def _copy_keystores(self):
            time.sleep(30)
            self._prepare_keystore_reuse_folders()
            self._copy_keystore(self.provider_datadir, self.provider_reuse_dir)
            self._copy_keystore(
                self.requestor_datadir, self.requestor_reuse_dir)

        def _prepare_keystore_reuse_folders(self) -> None:
            self.provider_reuse_dir = pathlib.Path(get_testdir()).parent \
                                      / 'provider_reuse_keystore'
            self.requestor_reuse_dir = pathlib.Path(get_testdir()).parent \
                                       / 'requestor_reuse_keystore'
            shutil.rmtree(self.provider_reuse_dir, ignore_errors=True)
            shutil.rmtree(self.requestor_reuse_dir, ignore_errors=True)
            print('Old temporary folders for reuse keystore.json removed')
            try:
                os.mkdir(self.provider_reuse_dir)
                os.mkdir(self.requestor_reuse_dir)
            except OSError:
                print('Unexpected problem with creating folders for keystore')
                raise

        @staticmethod
        def _copy_keystore(
                datadir: pathlib.PosixPath,
                reuse_dir: pathlib.PosixPath) -> None:
            src = str(datadir/'rinkeby/keys/keystore.json')
            dst = str(reuse_dir/'keystore.json')
            copyfile(src, dst)

        def __init__(self, provider_datadir, requestor_datadir):
            self.provider_datadir = provider_datadir
            self.requestor_datadir = requestor_datadir
            thread = Thread(target=self._copy_keystores)
            thread.start()

    def __new__(cls, provider_datadir: str, requestor_datadir: str):
        if cls.instance is None:
            cls.instance = ReuseNodeKeys.__ReuseNodeKeys(
                provider_datadir, requestor_datadir)
        else:
            cls.instance.first_test_in_set = False
        return ReuseNodeKeys.instance


class NodeTestBase:
    def setUp(self):
        test_dir = pathlib.Path(get_testdir()) / self._relative_id()
        self.provider_datadir = test_dir/'provider'
        self.requestor_datadir = test_dir/'requestor'
        os.makedirs(self.provider_datadir)
        os.makedirs(self.requestor_datadir)
        self.disable_keys_decorator = False
        self.first_test_in_set = ReuseNodeKeys(
            self.provider_datadir, self.requestor_datadir).first_test_in_set

    def _relative_id(self):
        from . import __name__ as parent_name
        return self.id().replace(parent_name + '.', '')

    def _should_node_keys_be_reused(self) -> bool:
        # It should be imported locally because may be changed in command line
        # and we need to get here updated value
        from conftest import DISABLE_KEY_REUSE_COMMAND_LINE
        if any([
            self.first_test_in_set,
            DISABLE_KEY_REUSE_COMMAND_LINE,
            self.disable_keys_decorator
        ]) is True:
            return False
        else:
            return True

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

        if self._should_node_keys_be_reused():
            self._replace_files_to_used_before()

        return subprocess.call(args=test_args)

    @staticmethod
    def _replace_keystore(destination: pathlib.PosixPath) -> None:
        src = pathlib.Path(get_testdir()).parent/'provider_reuse_keystore/' \
            'keystore.json' if 'provider' in str(destination) else pathlib.Path(
            get_testdir()).parent/'requestor_reuse_keystore/keystore.json'

        dst = destination/'rinkeby/keys/keystore.json'
        os.makedirs(str(destination/'rinkeby/keys'))
        copyfile(str(src), str(dst))

    def _replace_files_to_used_before(self):
        self._replace_keystore(self.provider_datadir)
        self._replace_keystore(self.requestor_datadir)
