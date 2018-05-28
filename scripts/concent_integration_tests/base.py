import base64
import logging
import calendar
import time

import golem_messages

from golem_messages import cryptography
from golem_messages import serializer
from golem_messages.message.base import Message
from golem_messages.message import concents as concent_msg

from golem.network.concent import client

from golem.core import variables


logger = logging.getLogger(__name__)


class ConcentBaseTest:
    # pylint:disable=no-member

    @staticmethod
    def _fake_keys():
        return cryptography.ECCx(None)

    def setUp(self):
        self.variant = variables.CONCENT_CHOICES['staging']
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
            'requestor_public_key': self.requestor_pub_key,
            'provider_public_key': self.provider_pub_key,
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

    # pylint:enable=no-member
