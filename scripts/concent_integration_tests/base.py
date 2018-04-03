from golem_messages import cryptography


class ConcentBaseTest:
    def setUp(self):
        self.keys = cryptography.ECCx(None)

    @property
    def priv_key(self):
        return self.keys.raw_privkey

    @property
    def pub_key(self):
        return self.keys.raw_pubkey
