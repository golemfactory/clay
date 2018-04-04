import faker
import golem_messages

from golem_messages import cryptography
from golem_messages.message.base import Message

from golem.network.concent import client

from golem.core import variables


class ConcentBaseTest:

    @staticmethod
    def _fake_keys():
        return cryptography.ECCx(faker.Faker().binary(length=32))

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

    def assertSameMessage(self, msg1, msg2):
        return self.assertEqual(msg1.get_short_hash(), msg2.get_short_hash())
