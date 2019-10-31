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
PASSWORD = 'goleM.8'

_logging = False


def _log(*args):
    # Private log function since pytest.tearDown() does not print logger
    if _logging:
        print(*args)


class NodeKeyReuseBase:
    # Base class for key reuse providers
    def begin_test(self, datadirs: Dict[NodeId, Path]) -> None:
        raise NotImplementedError()

    def end_test(self) -> None:
        raise NotImplementedError()


class NodeKeyReuseConfig:
    # Configuration singleton class for reusing keys
    # Selects the right provider ( subclass of NodeKeyReuseBase )
    # Based on command line arguments ( TBA: and enviromnet vars )
    instance: 'Optional[NodeKeyReuseConfig]' = None
    provider: Optional[NodeKeyReuseBase] = None
    enabled: bool = True

    # Provider specific variables
    use_granary: bool = False
    granary_hostname: Optional[str] = None
    local_reuse_dir: Optional[Path] = None

    @classmethod
    def get(cls):
        _log("NodeKeyReuseConfig.get() called.")
        if not cls.instance:
            cls.instance = cls()
            if cls.use_granary:
                print("key_reuse - granary selected:",
                      cls.granary_hostname or 'local golem-granary')
                cls.provider = NodeKeyReuseGranary(cls.granary_hostname)
            else:
                print("key_reuse - local folder selected:", cls.local_reuse_dir)
                assert cls.local_reuse_dir is not None, \
                    "ERROR: No folder for reuse, call set_dir() first"
                cls.provider = NodeKeyReuseLocalFolder(cls.local_reuse_dir)
        return cls.instance

    @classmethod
    def set_dir(cls, dir: Path):
        _log("NodeKeyReuseConfig.set_dir() called. dir=", dir)
        assert cls.provider is None, "ERROR: Can not set_dir() after get()"
        cls.local_reuse_dir = dir

    @classmethod
    def begin_test(cls, datadirs: Dict[NodeId, Path]):
        _log("NodeKeyReuseConfig.begin_test() called. dirs= ", datadirs)
        if cls.enabled and cls.provider:
            cls.provider.begin_test(datadirs)

    @classmethod
    def end_test(cls):
        _log("NodeKeyReuseConfig.end_test() called.")
        if cls.enabled and cls.provider:
            cls.provider.end_test()

    @classmethod
    def disable(cls):
        _log("NodeKeyReuseConfig.disable() called.")
        cls.enabled = False

    @classmethod
    def enable(cls):
        _log("NodeKeyReuseConfig.enable() called.")
        cls.enabled = True

    @classmethod
    def reset(cls):
        _log("NodeKeyReuseConfig.reset() called.")
        cls.instance = None

    @classmethod
    def enable_granary(cls, hostname: Optional[str] = None):
        _log("NodeKeyReuseConfig.enable_granary() called. host=", hostname)
        cls.use_granary = True
        cls.granary_hostname = hostname


class NodeKeyReuseLocalFolder(NodeKeyReuseBase):
    # Key reuse provider implementation that uses a local folder to store keys
    def __init__(self, test_dir: Path):
        self.dir: Path = test_dir / 'key_reuse'
        self.datadirs: Dict[NodeId, Path] = {}
        self._first_test = True

    def begin_test(self, datadirs: Dict[NodeId, Path]) -> None:
        _log("NodeKeyReuseLocalFolder.begin_test() called.")
        self.datadirs = datadirs

        if not self._first_test:
            _log("Moving keys from reuse-dirs to data-dirs")
            self._recycle_keys()

    def end_test(self) -> None:
        _log("NodeKeyReuseLocalFolder.end_test() called.")
        try:
            _log("Moving keys from data-dirs to reuse-dirs")
            self._copy_keystores()
        except FileNotFoundError:
            print('Copying keystores failed...')
            return

        self._first_test = False

    def _recycle_keys(self) -> None:
        # this is run before running second and later tests
        for i, datadir in enumerate(self.datadirs.values()):
            _log("NodeKeyReuseLocalFolder._recycle_keys() loop. "
                 "i", i, 'datadir', datadir)
            reuse_dir = self.dir / str(i)
            if not reuse_dir.exists():
                continue
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
        for i, datadir in enumerate(self.datadirs.values()):
            _log("NodeKeyReuseLocalFolder._copy_keystores() loop. "
                 "i", i, 'datadir', datadir)
            self._copy_keystore(
                datadir, self.dir / str(i))

    def _prepare_keystore_reuse_folders(self) -> None:
        # this is run after tests
        try:
            for i in range(len(self.datadirs)):
                reuse_dir = self.dir / str(i)
                _log("NodeKeyReuseLocalFolder._prepare_keystore_reuse_folders()"
                     "i", i, 'reuse_dir', reuse_dir)
                shutil.rmtree(reuse_dir, ignore_errors=True)
                os.makedirs(reuse_dir)
        except OSError:
            print('Unexpected problem with creating folders for keystore')
            raise

    @staticmethod
    def _copy_keystore(datadir: Path, reuse_dir: Path) -> None:
        src = str(datadir / KEYSTORE_DIR / KEYSTORE_FILE)
        dst = str(reuse_dir / KEYSTORE_FILE)
        _log("NodeKeyReuseLocalFolder._copy_keystore() file. "
             "src=", src, ", dst=", dst)
        shutil.copyfile(src, dst)


class NodeKeyReuseGranary(NodeKeyReuseBase):
    # Key reuse provider implementation that uses a remote granary to store keys
    def __init__(self, hostname: str):
        self.datadirs: Dict[NodeId, Path] = {}
        self.granary = Granary(hostname)

    def begin_test(self, datadirs: Dict[NodeId, Path]) -> None:
        self.datadirs = datadirs
        _log("NodeKeyReuseGranary.begin_test() called. "
             "Moving keys from granary to data-dirs")
        self._recycle_keys()

    def end_test(self) -> None:
        _log("NodeKeyReuseGranary.end_test() called.")
        try:
            _log("Moving keys from data-dirs to granary")
            self._copy_keystores()
        except FileNotFoundError:
            print('Copying keystores failed...')
            return

    def _recycle_keys(self) -> None:
        # this is run before tests
        for datadir in self.datadirs.values():
            account = self.granary.request_account()
            if account is not None:
                self._replace_keystore(
                    account, datadir
                )
            else:
                print("WARNING: No key from granary, will generate one")

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

        for datadir in self.datadirs.values():
            account = self._copy_keystore(datadir)
            if account:
                self.granary.return_account(account)

    @staticmethod
    def _copy_keystore(datadir: Path) -> Optional[Account]:

        src_key_dir = datadir / KEYSTORE_DIR
        src_ts_file = src_key_dir / TRANSACTION_FILE
        src_key_file = src_key_dir / KEYSTORE_FILE
        ts = '{}'
        keystore = None

        try:  # read tx.json
            with open(src_ts_file, 'r') as f:
                ts = f.read()
        except FileNotFoundError:
            _log('No tx.json, continue')
        try:  # read keystore.json
            with open(src_key_file, 'r') as f:
                keystore = json.load(f)
        except FileNotFoundError:
            _log('No File, no key')
            return None

        try:  # unlock the key
            priv_key = decode_keyfile_json(keystore, PASSWORD.encode('utf-8'))
        except ValueError:
            raise WrongPassword

        return Account(priv_key, ts)

    @staticmethod
    def _save_private_key(key, key_path: Path, password: str) -> None:
        keystore = create_keyfile_json(
            key,
            password.encode('utf-8'),
            iterations=1024,
        )
        with open(key_path, 'w') as f:
            json.dump(keystore, f)
