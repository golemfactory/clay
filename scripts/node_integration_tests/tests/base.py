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


def reuse_node_keys_default(default_option: bool)-> Callable:
    def decorator(test_function: Callable)-> Callable:
        @wraps(test_function)
        def wrap(*args, **kwargs) -> None:
            kwargs.update({'reuse_keys_default': default_option})
            test_function(*args, **kwargs)
        return wrap
    return decorator


class ReuseNodeKeys(object):
    instance = None

    class __ReuseNodeKeys:
        first_test_in_set = True

        def _copy_keystores(self):
            time.sleep(30)
            self._prepare_keystore_reuse_folders()
            self._copy_keystore(self.provider_datadir, self.provider_reuse_dir)
            self._copy_transaction_system(
                self.provider_datadir, self.provider_reuse_dir)
            self._copy_keystore(
                self.requestor_datadir, self.requestor_reuse_dir)
            self._copy_transaction_system(
                self.requestor_datadir, self.requestor_reuse_dir)

        def _prepare_keystore_reuse_folders(self) -> None:
            self.provider_reuse_dir = '/tmp/provider_reuse_keystore'
            self.requestor_reuse_dir = '/tmp/requestor_reuse_keystore'
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
        def _copy_keystore(datadir: str, reuse_dir: str) -> None:
            src = str(datadir) + '/rinkeby/keys/keystore.json'
            dst = str(reuse_dir) + '/keystore.json'
            copyfile(src, dst)

        @staticmethod
        def _copy_transaction_system(datadir: str, reuse_dir: str) -> None:
            src = str(datadir) + '/rinkeby/transaction_system/wallet.json'
            dst = str(reuse_dir) + '/wallet.json'
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
        self.provider_datadir = test_dir / 'provider'
        self.requestor_datadir = test_dir / 'requestor'
        os.makedirs(self.provider_datadir)
        os.makedirs(self.requestor_datadir)
        self.first_test_in_set = ReuseNodeKeys(
            self.provider_datadir, self.requestor_datadir).first_test_in_set

    def _relative_id(self):
        from . import __name__ as parent_name
        return self.id().replace(parent_name + '.', '')

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

        return subprocess.call(args=test_args)
