from unittest import TestCase

from golem.core.keysauth import mk_privkey, privtopub


def key_in_hex_with_colon_sep(key):
    return ':'.join(x.encode('hex') for x in key)


def key_in_hex(key):
    return key.encode('hex')


class TestKeygenHelper(TestCase):
    """Test vectors for keccak"""
    def test_mk_privkey(self):
        key = key_in_hex(mk_privkey(str("")))
        self.assertEqual(key, "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")

        key = key_in_hex(mk_privkey(str("abc")))
        self.assertEqual(key, "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")

        key = key_in_hex(mk_privkey(str("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")))
        self.assertEqual(key, "45d3b367a6904e6e8d502ee04999a7c27647f91fa845d456525fd352ae3d7371")

        key = key_in_hex(mk_privkey(str("ala")))
        self.assertEqual(key, "f5e06954a3a7c1ccaed8675b3fb429e23a839b5b406a72432bd6532dcd400d18")

        key = key_in_hex(mk_privkey(str("102")))
        self.assertEqual(key, "2a9063ed52b7d417e441f378325359c9ce274f5d6c3ecf11b7d42f24b9c90b7f")

        key = key_in_hex(mk_privkey(str("-4")))
        self.assertEqual(key, "702525ac629be223a9df40afdd83ad491268dd60af4e6703d2f71ef8a0b52408")

        key = key_in_hex(mk_privkey(str("0.234")))
        self.assertEqual(key, "2eac655c86354907b5a79706be2803d449fa3da2c66ee9cc0ee0e1b00e69f9da")

    def test_privtopub(self):
        key = key_in_hex(privtopub(mk_privkey(str(""))))
        self.assertEqual(key, "a63a07e888061ec9e8b64a3dc2937805c76089af36459305920373cd98a9f4ce15c27dbbe60928161eb62ae19f94ea48f399ce85e6db698520f3bcd4a9257157")

        key = key_in_hex(privtopub(mk_privkey(str("ala"))))
        self.assertEqual(key, "17c5529fc8eefc8689e466b93db2b84513db56813ce9a3404287633814d8b499fa4b667bb339d66d1cd724f4a3385ecbdb8c5038f5e04bfca6e6b4026fd7b9db")

        key = key_in_hex(privtopub(mk_privkey(str("102"))))
        self.assertEqual(key, "1ec23d1ac518015777e4600bc617144b0d04f3d8f4f69c945d553a40362a661a5dee4fcf75cfa274f8bee984e8d517ef3d23fa6a03e29b48e430dc7c983b2a89")

        key = key_in_hex(privtopub(mk_privkey(str("-4"))))
        self.assertEqual(key, "eaf8b04c5310fd1d9d614403d3450778f7bc2e141091499406963e02460a62edb8b25fc39a18fc840451fbeb83cf4a9d1570f158ab4d541d725bc135ed5e8c84")

        key = key_in_hex(privtopub(mk_privkey(str("0.234"))))
        self.assertEqual(key, "20c9df380ad77338a517b6df725d04e46eaa6d52e83385df4ae249dcdb50bebc11e5e4fd303949e2caa55abf62fff7945a3d710b8ed1cd955798b571e598ccf9")
