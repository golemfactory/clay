import json
import os
from pathlib import Path
import shutil
from typing import Dict, Optional

from eth_keyfile import create_keyfile_json, decode_keyfile_json

from golem.core.keysauth import WrongPassword
from tests.factories.granary import Granary, Account

from scripts.node_integration_tests.playbooks.test_config_base import NodeId

KEYSTORE_DIR = 'rinkeby/keys'
KEYSTORE_FILE = 'keystore.json'
TRANSACTION_FILE = 'tx.json'
PASSWORD = 'dupa.8'

_logging = False


class NodeKeyReuse:
    instance = None
    provider = None
    enabled = True
    granary_hostname = None

    @classmethod
    def get(cls, test_dir: Path):
        if not cls.instance:
            if _logging:
                print("NodeKeyReuse.get() called, no instance. "
                      "dir= ", test_dir)
            cls.instance = cls()
            if cls.granary_hostname:
                cls.provider = NodeKeyReuseGranary(cls.granary_hostname)
            else:
                cls.provider = NodeKeyReuseLocalFolder(test_dir)
        return cls.instance

    @classmethod
    def begin_test(cls, datadirs: Dict[NodeId, Path]):
        if cls.enabled and cls.provider:
            if _logging:
                print("NodeKeyReuse.begin_test() called. dirs= ", datadirs)
            cls.provider.begin_test(datadirs)

    @classmethod
    def end_test(cls):
        if cls.enabled and cls.provider:
            if _logging:
                print("NodeKeyReuse.end_test() called.")
            cls.provider.end_test()

    @classmethod
    def disable(cls):
        cls.enabled = False

    @classmethod
    def enable(cls):
        cls.enabled = True

    @classmethod
    def set_granary(cls, hostname):
        cls.granary_hostname = hostname


class NodeKeyReuseLocalFolder():
    def __init__(self, test_dir: Path):
        self.dir: Path = test_dir / 'key_reuse'
        self.datadirs: Dict[NodeId, Path] = {}
        self._first_test = True

    def begin_test(self, datadirs: Dict[NodeId, Path]) -> None:
        self.datadirs = datadirs
        if _logging:
            print("NodeKeyReuseLocalFolder.begin_test() called.")
        if not self._first_test:
            if _logging:
                print("Moving keys from reuse-dirs to data-dirs")
            self._recycle_keys()

    def end_test(self) -> None:
        print("NodeKeyReuseLocalFolder.end_test() called.")
        try:
            if _logging:
                print("Moving keys from data-dirs to reuse-dirs")
            self._copy_keystores()
        except FileNotFoundError:
            print('Copying keystores failed...')
            return

        self._first_test = False

    def _recycle_keys(self) -> None:
        # this is run before running second and later tests
        for i, node_id in enumerate(self.datadirs):
            datadir = self.datadirs[node_id]
            reuse_dir = self.dir / str(i)
            if not reuse_dir.exists():
                continue
            if _logging:
                print("NodeKeyReuseLocalFolder._copy_keystores() loop. "
                      "dir= ", datadir)
            self._replace_keystore(reuse_dir, datadir)

    @staticmethod
    def _replace_keystore(src: Path, dst: Path) -> None:
        src_file = src / KEYSTORE_FILE
        dst_file = dst / KEYSTORE_DIR / KEYSTORE_FILE
        os.makedirs(str(dst / KEYSTORE_DIR))
        shutil.copyfile(str(src_file), str(dst_file))

    def _copy_keystores(self) -> None:
        # this is run after tests
        self._prepare_keystore_reuse_folders()
        for i, node_id in enumerate(self.datadirs):
            datadir = self.datadirs[node_id]
            if _logging:
                print("NodeKeyReuseLocalFolder._copy_keystores() loop. "
                      "dir= ", datadir)
            self._copy_keystore(
                datadir, self.dir / str(i))

    def _prepare_keystore_reuse_folders(self) -> None:
        # this is run after tests
        try:
            for i in range(len(self.datadirs)):
                reuse_dir = self.dir / str(i)
                shutil.rmtree(reuse_dir, ignore_errors=True)
                os.makedirs(reuse_dir)
        except OSError:
            print('Unexpected problem with creating folders for keystore')
            raise

    @staticmethod
    def _copy_keystore(datadir: Path, reuse_dir: Path) -> None:
        src = str(datadir / KEYSTORE_DIR / KEYSTORE_FILE)
        dst = str(reuse_dir / KEYSTORE_FILE)
        if _logging:
            print("NodeKeyReuseLocalFolder._copy_keystore() file. "
                  "src=", src, ", dst=", dst)
        shutil.copyfile(src, dst)


class NodeKeyReuseGranary():
    def __init__(self, hostname: str):
        self.datadirs: Dict[NodeId, Path] = {}
        self.granary = Granary(hostname)

    def begin_test(self, datadirs: Dict[NodeId, Path]) -> None:
        self.datadirs = datadirs
        if _logging:
            print("NodeKeyReuseGranary.begin_test() called.")
        if _logging:
            print("Moving keys from granary to data-dirs")
            self._recycle_keys()

    def end_test(self) -> None:
        print("NodeKeyReuseGranary.end_test() called.")
        try:
            if _logging:
                print("Moving keys from data-dirs to granary")
            self._copy_keystores()
        except FileNotFoundError:
            print('Copying keystores failed...')
            return

    def _recycle_keys(self) -> None:
        print("Recycle keys")
        # this is run before running second and later tests
        for i, node_id in enumerate(self.datadirs):
            account = self.granary.request_account()
            if account is not None:
                self._replace_keystore(
                    account, self.datadirs[node_id]
                )

    def _replace_keystore(self, account: Account, dst: Path) -> None:
        dst_key_dir = dst / KEYSTORE_DIR
        dst_key_file = dst_key_dir / KEYSTORE_FILE
        dst_trans_file = dst_key_dir / TRANSACTION_FILE
        os.makedirs(str(dst_key_dir))
        self._save_private_key(account.raw_key, dst_key_file, PASSWORD)
        if account.transaction_store:
            dst_trans_file.write_text(account.transaction_store)

    def _copy_keystores(self):
        # this is run after tests
        # return key to granary as binary private key and transactions.json

        for i, node_id in enumerate(self.datadirs):
            account = self._copy_keystore(self.datadirs[node_id])
            if account:
                self.granary.return_account(account)

    @staticmethod
    def _copy_keystore(datadir: Path) -> Optional[Account]:

        src_key_dir = datadir / KEYSTORE_DIR
        src_ts_file = src_key_dir / TRANSACTION_FILE
        src_key_file = src_key_dir / KEYSTORE_FILE
        ts = None
        keystore = None

        try:  # read tx.json
            with open(src_ts_file, 'r') as f:
                ts = f.read()
        except FileNotFoundError:
            print('No tx.json, continue')
        try:  # read keystore.json
            with open(src_key_file, 'r') as f:
                keystore = f.read()
        except FileNotFoundError:
            print('No File, no key')
            return None
        keystore = json.loads(keystore)

        try:  # unlock the key
            priv_key = decode_keyfile_json(keystore, PASSWORD.encode('utf-8'))
        except ValueError:
            raise WrongPassword

        return Account(priv_key, ts)

    @staticmethod
    def _save_private_key(key, key_path: Path, password: str) -> None:
        print("_save_private_key")
        print(password)
        keystore = create_keyfile_json(
            key,
            password.encode('utf-8'),
            iterations=1024,
        )
        with open(key_path, 'w') as f:
            f.write(json.dumps(keystore))
