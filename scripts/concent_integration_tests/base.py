import faker
import golem_messages

from golem_messages import cryptography
from golem_messages.message.base import Message

from golem.network.concent import client

from golem.core import variables


class ConcentBaseTest:
    def setUp(self):
        self.keys = cryptography.ECCx(faker.Faker().binary(length=32))

    @property
    def priv_key(self):
        return self.keys.raw_privkey

    @property
    def pub_key(self):
        return self.keys.raw_pubkey

    def _send_to_concent(self, msg: Message, signing_key=None, public_key=None):
        return client.send_to_concent(
            msg,
            signing_key or self.priv_key,
            public_key or self.pub_key
        )

    def _load_response(self, response):
        return golem_messages.load(
            response,
            self.priv_key,
            variables.CONCENT_PUBKEY,
        )
