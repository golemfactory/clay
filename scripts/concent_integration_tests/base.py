# pylint: disable=protected-access,no-member
import base64
import calendar
import datetime
import logging
import os
import random
import sys
import threading
import time

import golem_messages

from golem_messages import cryptography
from golem_messages import helpers
from golem_messages import serializer
from golem_messages import utils as msg_utils
from golem_messages.message.base import Message
from golem_messages.message import concents as concent_msg

from golem import testutils
from golem.core import variables
from golem.network.concent import client
from golem.transactions.ethereum import ethereumtransactionsystem as libets


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

    def receive_from_concent(self, signing_key=None, public_key=None):
        return client.receive_from_concent(
            signing_key=signing_key or self.provider_priv_key,
            public_key=public_key or self.provider_pub_key,
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

    def provider_receive(self):
        response = self.receive_from_concent()
        if not response:
            logger.debug("Provider got empty response")
            return None

        msg = self.provider_load_response(response)
        logger.debug("Provider receives %s", msg)
        return msg

    def requestor_receive(self):
        response = self.receive_from_concent(
            signing_key=self.requestor_keys.raw_privkey,
            public_key=self.requestor_keys.raw_pubkey
        )
        if not response:
            logger.debug("Requestor got empty response")
            return None

        msg = self.requestor_load_response(response)
        logger.debug("Requestor receives %s", msg)
        return msg

    def _load_response(self, response, priv_key):
        if response is None:
            return None
        return golem_messages.load(
            response, priv_key, self.variant['pubkey'])

    def provider_load_response(self, response):
        return self._load_response(response, self.provider_priv_key)

    def requestor_load_response(self, response):
        return self._load_response(response, self.requestor_priv_key)

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


class ETSBaseTest(ConcentBaseTest, testutils.DatabaseFixture):
    """Base test with ets attribute"""

    def setUp(self):
        random.seed()
        ConcentBaseTest.setUp(self)
        testutils.DatabaseFixture.setUp(self)
        self.ets = libets.EthereumTransactionSystem(
            datadir=self.tempdir,
            node_priv_key=self.requestor_keys.raw_privkey,
        )

    def wait_for_gntb(self):
        sys.stderr.write('Waiting for GNTB...\n')
        while self.ets._gntb_balance <= 0:
            try:
                self.ets._run()
            except ValueError as e:
                # web3 will raise ValueError if 'error' is present
                # in response from geth
                sys.stderr.write('E: {}\n'.format(e))
            sys.stderr.write(
                'Still waiting. GNT: {:22} GNTB: {:22} ETH: {:17}\n'.format(
                    self.ets._gnt_balance,
                    self.ets._gntb_balance,
                    self.ets._eth_balance,
                ),
            )
            time.sleep(10)

    def requestor_put_deposit(self, price: int):
        start = datetime.datetime.now()
        self.wait_for_gntb()
        amount, _ = helpers.requestor_deposit_amount(
            # We'll use subtask price. Total number of subtasks is unknown
            price,
        )

        transaction_processed = threading.Event()

        def _callback():
            transaction_processed.set()

        self.ets.concent_deposit(
            required=amount,
            expected=amount,
            reserved=0,
            cb=_callback,
        )
        while not transaction_processed.is_set():
            sys.stderr.write('.')
            sys.stderr.flush()
            self.ets._sci._monitor_blockchain_single()
            time.sleep(15)
        sys.stderr.write("\nDeposit confirmed in {}\n".format(
            datetime.datetime.now()-start))
        if self.ets.concent_balance() < amount:
            raise RuntimeError("Deposit failed")
