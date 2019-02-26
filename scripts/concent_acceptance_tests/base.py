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
import typing
import unittest

from pathlib import Path

from ethereum.utils import denoms
import golem_messages

from golem_messages import cryptography
from golem_messages import helpers
from golem_messages import serializer
from golem_messages import utils as msg_utils
from golem_messages.message.base import Message
from golem_messages.message import concents

from golem_sci import (
    new_sci_rpc, SmartContractsInterface, JsonTransactionsStorage)

from golem.core import variables
from golem.ethereum.transactionsystem import tETH_faucet_donate
from golem.network.concent import client
from golem.utils import privkeytoaddr

logger = logging.getLogger(__name__)


def dump_balance(sci: SmartContractsInterface):
    gnt = sci.get_gnt_balance(sci.get_eth_address())
    gntb = sci.get_gntb_balance(sci.get_eth_address())
    eth = sci.get_eth_balance(sci.get_eth_address())
    deposit = sci.get_deposit_value(sci.get_eth_address())
    balance_str = (
        "[Balance] ETH=%.18f GNT=%.18f"
        " GNTB=%.18f DEPOSIT=%.18f ADDR:%s\n"
    )
    balance_str %= (
        eth / denoms.ether,
        gnt / denoms.ether,
        gntb / denoms.ether,
        deposit / denoms.ether,
        sci.get_eth_address(),
    )
    sys.stderr.write(balance_str)


class ConcentBaseTest(unittest.TestCase):
    @staticmethod
    def _fake_keys():
        return cryptography.ECCx(None)

    def setUp(self):
        from golem.config.environments import set_environment
        concent_variant = os.environ.get('CONCENT_VARIANT', 'staging')
        set_environment('testnet', concent_variant)
        self.variant = variables.CONCENT_CHOICES[concent_variant]
        self.provider_keys = self._fake_keys()
        self.requestor_keys = self._fake_keys()
        from golem.core import common
        common.config_logging(suffix='concent-acceptance')
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
        encoded_requestor_pubkey = msg_utils.encode_hex(self.requestor_pub_key)
        kwargs = {
            'sign__privkey': self.requestor_priv_key,
            'ethsig__privkey': self.requestor_priv_key,
            'requestor_public_key': encoded_requestor_pubkey,
            'requestor_ethereum_public_key': encoded_requestor_pubkey,
            'want_to_compute_task__provider_public_key':
                msg_utils.encode_hex(self.provider_pub_key),
            'want_to_compute_task__sign__privkey':
                self.provider_priv_key,
            'want_to_compute_task__task_header__requestor_public_key':
                encoded_requestor_pubkey,
            'want_to_compute_task__task_header__sign__privkey':
                self.requestor_priv_key,
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

    def provider_receive(self):
        return self.receive_from_concent(
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

    def assertServiceRefused(
            self,
            msg: concents.ServiceRefused,
            reason=None,
        ):
        self.assertIsInstance(msg, concents.ServiceRefused)
        if reason:
            self.assertEqual(msg.reason, reason)

    def assertFttCorrect(self, ftt, subtask_id, client_key, operation):
        self.assertIsInstance(ftt, concents.FileTransferToken)

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

    @staticmethod
    def _log_concent_response(response):
        logger.debug(
            "Concent response - status: %s, head: '%s', body: '%s'",
            response.status_code, response.headers, response.content
        )


class SCIBaseTest(ConcentBaseTest):
    """
    Base test providing instances of TransactionSystem
    for the provider and the requestor
    """

    def setUp(self):
        super().setUp()
        from golem.config.environments.testnet import EthereumConfig
        random.seed()

        self.transaction_timeout = datetime.timedelta(seconds=300)
        self.sleep_interval = 15

        requestor_storage = JsonTransactionsStorage(
            Path(tempfile.mkdtemp()) / 'tx.json')
        provider_storage = JsonTransactionsStorage(
            Path(tempfile.mkdtemp()) / 'tx.json')

        self.requestor_eth_addr = privkeytoaddr(self.requestor_keys.raw_privkey)
        self.provider_eth_addr = privkeytoaddr(self.provider_keys.raw_privkey)

        self.requestor_sci = new_sci_rpc(
            storage=requestor_storage,
            rpc=EthereumConfig.NODE_LIST[0],
            address=self.requestor_eth_addr,
            tx_sign=lambda tx: tx.sign(self.requestor_keys.raw_privkey),
            contract_addresses=EthereumConfig.CONTRACT_ADDRESSES,
            chain=EthereumConfig.CHAIN,
        )
        self.provider_sci = new_sci_rpc(
            storage=provider_storage,
            rpc=EthereumConfig.NODE_LIST[0],
            address=self.provider_eth_addr,
            tx_sign=lambda tx: tx.sign(self.provider_keys.raw_privkey),
            contract_addresses=EthereumConfig.CONTRACT_ADDRESSES,
            chain=EthereumConfig.CHAIN,
        )

    # pylint: disable=too-many-arguments
    def retry_until_timeout(
            self,
            condition: typing.Callable,
            timeout_message: str = '',
            timeout: typing.Optional[datetime.timedelta] = None,
            sleep_interval: typing.Optional[float] = None,
            sleep_action: typing.Optional[typing.Callable] =
            lambda: (sys.stderr.write('.'), sys.stderr.flush()),  # type: ignore
    ):
        if sleep_interval is None:
            sleep_interval = self.sleep_interval

        if timeout is None:
            timeout = self.transaction_timeout

        start = datetime.datetime.now()

        while condition():
            if sleep_action:
                sleep_action()
            time.sleep(sleep_interval)  # type: ignore
            if start + timeout < datetime.datetime.now():  # type: ignore
                raise TimeoutError(timeout_message)
        return start, datetime.datetime.now()

    def wait_for_gntb(self, sci: SmartContractsInterface):
        sys.stderr.write('Waiting for GNT\n')
        sci.request_gnt_from_faucet()
        sci.open_gate()

        self.retry_until_timeout(
            lambda: (sci.get_gnt_balance(sci.get_eth_address()) == 0 or
                     sci.get_gate_address() is None),
            "Acquiring GNT timed out",
        )

        sys.stderr.write('Got GNT, waiting for GNTB...\n')

        sci.transfer_gnt(sci.get_gate_address(),
                         sci.get_gnt_balance(sci.get_eth_address()))
        sci.transfer_from_gate()

        self.retry_until_timeout(
            lambda: sci.get_gntb_balance(sci.get_eth_address()) == 0,
            "GNTB conversion timed out",
        )

        sys.stderr.write('Got GNTB...\n')
        dump_balance(sci)

    def put_deposit(self, sci: SmartContractsInterface, amount: int):
        # 0) get tETH from faucet
        # 1) -> request GNT from faucet `request_gnt_from_faucet`
        # 2) `on_transaction_complete`
        # 3) GNTConverter -> convert + is_converting
        # 4) sci.get_gntb_balance
        # 5) sci.concent_deposit + `on_transaction_confirmed`

        self.assertGreater(amount, 0)

        sys.stderr.write(
            'Deposit contract %s\nRequired confirmations: %d\n' % (
                sci._gntdeposit.address,
                sci.REQUIRED_CONFS,
            ),
        )

        sys.stderr.write('Calling tETH faucet...\n')
        self.retry_until_timeout(
            lambda: not tETH_faucet_donate(sci.get_eth_address()),
            "Faucet timed out",
        )

        sys.stderr.write('Waiting for tETH...\n')
        self.retry_until_timeout(
            lambda: sci.get_eth_balance(sci.get_eth_address()) == 0,
            "Acquiring tETH timed out",
        )

        self.wait_for_gntb(sci)

        deposit = False

        def deposit_confirmed(_):
            nonlocal deposit
            deposit = True
        sys.stderr.write(
            'Depositing %.8f GNTB...\n' % (amount / denoms.ether, ),
        )
        tx_hash = sci.deposit_payment(amount)
        sci.on_transaction_confirmed(tx_hash, deposit_confirmed)

        self.retry_until_timeout(
            lambda: not deposit,
            "Deposit timed out.",
            sleep_interval=1,
        )

        sys.stderr.write("\nDeposit confirmed\n")

        if sci.get_deposit_value(sci.get_eth_address()) < amount:
            raise RuntimeError("Deposit failed")
        self.blockchain_sleep(120)
        dump_balance(sci)

    def requestor_put_deposit(self, price: int):
        amount, _ = helpers.requestor_deposit_amount(
            # We'll use subtask price. Total number of subtasks is unknown
            price,
        )
        return self.put_deposit(self.requestor_sci, amount)

    def provider_put_deposit(self, price: int):
        amount, _ = helpers.provider_deposit_amount(price)
        return self.put_deposit(self.provider_sci, amount)

    @staticmethod
    def blockchain_sleep(sleep_time=60):
        sys.stderr.write(f'Going to sleep for: {sleep_time} seconds...\n')
        time.sleep(sleep_time)
