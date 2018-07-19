# pylint: disable=protected-access,no-member
import base64
import calendar
import datetime
import functools
import logging
import os
import random
import sys
import tempfile
import time
import unittest

from pathlib import Path

import golem_messages

from golem_messages import cryptography
from golem_messages import helpers
from golem_messages import serializer
from golem_messages import utils as msg_utils
from golem_messages.message.base import Message
from golem_messages.message import concents as concent_msg

from golem_sci import (
    new_sci_rpc, SmartContractsInterface, JsonTransactionsStorage)

from golem.config.environments.testnet import EthereumConfig

from golem.core import variables
from golem.database import Database
from golem.model import DB_MODELS, db, DB_FIELDS
from golem.network.concent import client
from golem.utils import privkeytoaddr

# igor contradicts himself ;p
from golem.transactions.ethereum.ethereumtransactionsystem import (
    tETH_faucet_donate)

logger = logging.getLogger(__name__)


class ConcentBaseTest:
    @staticmethod
    def _fake_keys():
        return cryptography.ECCx(None)

    def setUp(self):
        concent_variant = os.environ.get('CONCENT_VARIANT', 'staging')
        self.variant = variables.CONCENT_CHOICES[concent_variant]
        self.provider_keys = self._fake_keys()
        self.requestor_keys = self._fake_keys()
        logger.debug('Provider key: %s',
                     base64.b64encode(self.provider_pub_key).decode())
        logger.debug('Requestor key: %s',
                     base64.b64encode(self.requestor_pub_key).decode())

    @property
    def provider_priv_key(self):
        return self.provider_keys.raw_privkey

    @property
    def provider_pub_key(self):
        return self.provider_keys.raw_pubkey

    @property
    def requestor_priv_key(self):
        return self.requestor_keys.raw_privkey

    @property
    def requestor_pub_key(self):
        return self.requestor_keys.raw_pubkey

    def gen_ttc_kwargs(self, prefix=''):
        kwargs = {
            'sign__privkey': self.requestor_priv_key,
            'requestor_public_key': msg_utils.encode_hex(
                self.requestor_pub_key,
            ),
            'provider_public_key': msg_utils.encode_hex(self.provider_pub_key),
        }
        return {prefix + k: v for k, v in kwargs.items()}

    def gen_rtc_kwargs(self, prefix=''):
        kwargs = {'sign__privkey': self.provider_priv_key}
        return {prefix + k: v for k, v in kwargs.items()}

    def send_to_concent(self, msg: Message, signing_key=None):
        return client.send_to_concent(
            msg,
            signing_key=signing_key or self.provider_priv_key,
            concent_variant=self.variant,
        )

    def provider_send(self, msg):
        logger.debug("Provider sends %s", msg)
        return self.send_to_concent(
            msg,
            signing_key=self.provider_keys.raw_privkey
        )

    def requestor_send(self, msg):
        logger.debug("Requestor sends %s", msg)
        return self.send_to_concent(
            msg,
            signing_key=self.requestor_keys.raw_privkey
        )

    def receive_and_load(self, actor, receive_function, private_key, **kwargs):
        response = receive_function(
            concent_variant=self.variant,
            **kwargs,
        )
        if not response:
            logger.debug("%s got empty response", actor)
            return None
        msg = self._load_response(response, private_key)
        logger.debug("%s receives %s", actor, msg)
        return msg

    receive_from_concent = functools.partialmethod(
        receive_and_load,
        receive_function=client.receive_from_concent,
    )
    receive_out_of_band = functools.partialmethod(
        receive_and_load,
        receive_function=client.receive_out_of_band,
    )

    def provider_receive(self):
        return self.receive_from_concent(
            actor='Provider',
            signing_key=self.provider_priv_key,
            private_key=self.provider_priv_key,
            public_key=self.provider_pub_key,
        )

    def provider_receive_oob(self):
        return self.receive_out_of_band(
            actor='Provider',
            signing_key=self.provider_priv_key,
            private_key=self.provider_priv_key,
            public_key=self.provider_pub_key,
        )

    def requestor_receive(self):
        return self.receive_from_concent(
            actor='Requestor',
            signing_key=self.requestor_keys.raw_privkey,
            private_key=self.requestor_keys.raw_privkey,
            public_key=self.requestor_keys.raw_pubkey
        )

    def requestor_receive_oob(self):
        return self.receive_out_of_band(
            actor='Requestor',
            signing_key=self.requestor_keys.raw_privkey,
            private_key=self.requestor_keys.raw_privkey,
            public_key=self.requestor_keys.raw_pubkey
        )

    def _load_response(self, response, priv_key):
        if response is None:
            return None
        return golem_messages.load(
            response, priv_key, self.variant['pubkey'])

    def provider_load_response(self, response):
        msg = self._load_response(response, self.provider_priv_key)
        logger.debug("Provider receives %s", msg)
        return msg

    def requestor_load_response(self, response):
        msg = self._load_response(response, self.requestor_priv_key)
        logger.debug("Requestor receives %s", msg)
        return msg

    def assertSamePayload(self, msg1, msg2):
        dump1 = serializer.dumps(msg1.slots())
        dump2 = serializer.dumps(msg2.slots())
        return self.assertEqual(
            dump1,
            dump2,
            msg="Message payload differs: \n\n%s\n\n%s" % (
                msg1.slots(), msg2.slots()
            )
        )

    def assertFttCorrect(self, ftt, subtask_id, client_key, operation):
        self.assertIsInstance(ftt, concent_msg.FileTransferToken)

        self.assertIsNotNone(subtask_id)  # sanity check, just in case
        self.assertEqual(ftt.subtask_id, subtask_id)

        self.assertEqual(
            client_key,
            ftt.authorized_client_public_key
        )
        self.assertGreater(
            ftt.token_expiration_deadline,
            calendar.timegm(time.gmtime())
        )
        self.assertEqual(ftt.operation, operation)

    # pylint:enable=no-member

    @staticmethod
    def _log_concent_response(response):
        logger.debug(
            "Concent response - status: %s, head: '%s', body: '%s'",
            response.status_code, response.headers, response.content
        )


class ETSBaseTest(ConcentBaseTest, unittest.TestCase):
    """
    Base test providing instances of EthereumTransactionSystem
    for the provider and the requestor
    """

    def setUp(self):
        super(ETSBaseTest, self).setUp()
        random.seed()

        self.transaction_timeout = datetime.timedelta(seconds=300)
        self.sleep_interval = 15

        td_requestor = tempfile.mkdtemp()
        td_provider = tempfile.mkdtemp()

        requestor_storage = JsonTransactionsStorage(
            Path(td_requestor) / 'tx.json')
        provider_storage = JsonTransactionsStorage(
            Path(td_provider) / 'tx.json')

        self.database_requestor = Database(
            db, fields=DB_FIELDS, models=DB_MODELS, db_dir=td_requestor)
        self.database_provider = Database(
            db, fields=DB_FIELDS, models=DB_MODELS, db_dir=td_provider)

        self.requestor_eth_addr = privkeytoaddr(self.requestor_keys.raw_privkey)
        self.provider_eth_addr = privkeytoaddr(self.provider_keys.raw_privkey)

        self.requestor_sci = new_sci_rpc(
            storage=requestor_storage,
            rpc=EthereumConfig.NODE_LIST[0],
            address=self.requestor_eth_addr,
            tx_sign=lambda tx: tx.sign(self.requestor_keys.raw_privkey),
            chain=EthereumConfig.CHAIN,
        )
        self.requestor_sci.REQUIRED_CONFS = 1
        self.provider_sci = new_sci_rpc(
            storage=provider_storage,
            rpc=EthereumConfig.NODE_LIST[0],
            address=self.provider_eth_addr,
            tx_sign=lambda tx: tx.sign(self.provider_keys.raw_privkey),
            chain=EthereumConfig.CHAIN,
        )
        self.provider_sci.REQUIRED_CONFS = 1

    def wait_for_gntb(self, sci: SmartContractsInterface):
        start = datetime.datetime.now()
        sys.stderr.write('Waiting for GNT\n')
        sci.request_gnt_from_faucet()
        sci.open_gate()

        while (sci.get_gnt_balance(sci.get_eth_address()) == 0 or
               sci.get_gate_address() is None):
            if start + self.transaction_timeout < datetime.datetime.now():
                raise TimeoutError("Acquiring GNT timed out")
            time.sleep(self.sleep_interval)

        sys.stderr.write('Got GNT...\n')

        start = datetime.datetime.now()
        sci.transfer_gnt(sci.get_gate_address(),
                         sci.get_gnt_balance(sci.get_eth_address()))
        sci.transfer_from_gate()

        while sci.get_gntb_balance(sci.get_eth_address()) == 0:
            if start + self.transaction_timeout < datetime.datetime.now():
                raise TimeoutError("GNTB conversion timed out")
            time.sleep(self.sleep_interval)

        sys.stderr.write('Got GNTB...\n')

    def put_deposit(self, sci: SmartContractsInterface, amount: int):
        # 0) get tETH from faucet
        # 1) -> request GNT from faucet `request_gnt_from_faucet`
        # 2) `on_transaction_complete`
        # 3) GNTConverter -> convert + is_converting
        # 4) sci.get_gntb_balance
        # 5) sci.concent_deposit + `on_transaction_confirmed`

        start = datetime.datetime.now()

        if not tETH_faucet_donate(sci.get_eth_address()):
            raise RuntimeError("Could not acquire tETH")

        while not sci.get_eth_balance(sci.get_eth_address()) > 0:
            sys.stderr.write('Waiting for tETH...\n')
            time.sleep(self.sleep_interval)
            if start + self.transaction_timeout < datetime.datetime.now():
                raise TimeoutError("Acquiring tETH timed out")

        self.wait_for_gntb(sci)

        start2 = datetime.datetime.now()
        deposit = False

        def deposit_confirmed(_):
            nonlocal deposit
            deposit = True

        tx_hash = sci.deposit_payment(amount)
        sci.on_transaction_confirmed(tx_hash, deposit_confirmed)

        while not deposit:
            if start2 + self.transaction_timeout < datetime.datetime.now():
                raise TimeoutError("Deposit timed out.")

        sys.stderr.write("\nDeposit confirmed in {}\n".format(
            datetime.datetime.now()-start))

        if sci.get_deposit_value(sci.get_eth_address()) < amount:
            raise RuntimeError("Deposit failed")

    def requestor_put_deposit(self, price: int):
        amount, _ = helpers.requestor_deposit_amount(
            # We'll use subtask price. Total number of subtasks is unknown
            price,
        )
        return self.put_deposit(self.requestor_sci, amount)

    def provider_put_deposit(self, price: int):
        amount, _ = helpers.provider_deposit_amount(price)
        return self.put_deposit(self.provider_sci, amount)
