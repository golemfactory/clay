import base64
import calendar
import time

import golem_messages

from golem_messages import cryptography
from golem_messages import serializer
from golem_messages.message.base import Message
from golem_messages.message import concents as concent_msg

from golem.network.concent import client

from golem.core import variables


class ConcentBaseTest:
    # pylint:disable=no-member

    @staticmethod
    def _fake_keys():
        return cryptography.ECCx(None)

    def setUp(self):
        self.keys = self._fake_keys()
        self.op_keys = self._fake_keys()

    @property
    def priv_key(self):
        return self.keys.raw_privkey

    @property
    def pub_key(self):
        return self.keys.raw_pubkey

    def _send_to_concent(
            self, msg: Message,
            signing_key=None,
            public_key=None,
            other_party_public_key=None):
        return client.send_to_concent(
            msg,
            signing_key or self.priv_key,
            public_key or self.pub_key,
            other_party_public_key=other_party_public_key,
        )

    def _load_response(self, response, priv_key=None):
        return golem_messages.load(
            response,
            priv_key or self.priv_key,
            variables.CONCENT_PUBKEY,
        )

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
            base64.standard_b64decode(ftt.authorized_client_public_key)
        )
        self.assertGreater(
            ftt.token_expiration_deadline,
            calendar.timegm(time.gmtime())
        )
        self.assertEqual(ftt.operation, operation)

    # pylint:enable=no-member
