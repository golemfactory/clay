import json
import os

from ethereum.keys import PBKDF2_CONSTANTS

from golem.testutils import TempDirFixture
from golem.ethereum.accounts import Account

PBKDF2_CONSTANTS['c'] = 1000  # Limit KDF difficulty.


class EthereumAccountTest(TempDirFixture):

    def test_new_account_save(self) -> None:
        keyfile = os.path.join(self.tempdir, 'a')
        a = Account.new('pass', path=keyfile)
        a.save()

        assert os.path.getsize(keyfile) > 20
        assert json.load(open(keyfile))

        b = Account.load(keyfile)
        assert a.address == b.address

        with self.assertRaises(ValueError) as context:
            b.unlock('wrong password')
            assert 'password' in context
