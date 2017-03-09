from unittest import TestCase

from golem.core.keysauth import mk_privkey, privtopub


def key_in_hex(key):
    return ''.join(x.encode('hex') for x in key)


class TestKeygenHelper(TestCase):
    """First three test vectors from http://www.di-mgt.com.au/sha_testvectors.html"""
    def test_mk_privkey(self):
        key = key_in_hex(mk_privkey(str("")))
        self.assertEqual(key, "a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a")

        key = key_in_hex(mk_privkey(str("abc")))
        self.assertEqual(key, "3a985da74fe225b2045c172d6bd390bd855f086e3e9d525b46bfe24511431532")

        key = key_in_hex(mk_privkey(str("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")))
        self.assertEqual(key, "41c0dba2a9d6240849100376a8235e2c82e1b9998a999e21db32dd97496d3376")

        key = key_in_hex(mk_privkey(str("ala")))
        self.assertEqual(key, "dd8a216367a5616f25cef9dc48eda86d6ea68cb59f9f0df69af34914e3ce7750")

        key = key_in_hex(mk_privkey(str("102")))
        self.assertEqual(key, "3672ce6ff46ae74b281fcb27881affd18e54e3efacc11031364b69416c9264b1")

        key = key_in_hex(mk_privkey(str("-4")))
        self.assertEqual(key, "738d11181b63c51590e9b6c74266b803094ef05436748edf0b265c757d77a576")

        key = key_in_hex(mk_privkey(str("0.234")))
        self.assertEqual(key, "6fad32c106f730f4b483d2d357525d6379b4ebadae1e00061a95abc5b37ae678")

    def test_privtopub(self):
        key = key_in_hex(privtopub(mk_privkey(str(""))))
        self.assertEqual(key, "c988c298ec514516121176a5117c8a4f9692914b0e197d2d425d733f83e41b891ed9b82459328c1ab7e3c20507c86e8bead9320b950c565609f860ebb5377088")

        key = key_in_hex(privtopub(mk_privkey(str("ala"))))
        self.assertEqual(key, "88aaea31f42c37a429ba5a7a522d0a006fb681ce20cdfc852f618ee680228a2ed0aeaa72e29c059d589ed08c6425c3d740056860f369c8be0e3c8b6970d17ab4")

        key = key_in_hex(privtopub(mk_privkey(str("102"))))
        self.assertEqual(key, "78b9325c466c77f4ac350fee377503e70d49d2924a54bdeb214c3c6fdad4e2c80f160b69f23dc60e1eda4b30529ea11113b7a5c0331c87faa07c2984fa9ecaaa")

        key = key_in_hex(privtopub(mk_privkey(str("-4"))))
        self.assertEqual(key, "9d36a5fe87b28aaf8867a431672a4ff337f751ab74e8c9bf9bcbd5ee3354ab91749089aa4725b81bcd97d2e81dae3d74e1e01844387498c77d9f0d9b36b5c4c1")

        key = key_in_hex(privtopub(mk_privkey(str("0.234"))))
        self.assertEqual(key, "2cb335f6f2a5262cbab585104737d6b156fb6e2073f191e435b6340fd6903bd5d3f19135db082843881e4096d75db4c35484a5fd8acc3085ca0884f5a45cfa64")
