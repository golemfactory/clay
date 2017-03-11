# Based on https://github.com/ethereum/pydevp2p/blob/develop/devp2p/tests/test_crypto.py
#
#
# The MIT License (MIT)
#
# Copyright (c) 2015 Heiko Hees
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#

import random
from unittest import TestCase
from golem.core import crypto


def get_ecc(secret=''):
    return crypto.ECCx(raw_privkey=crypto.mk_privkey(secret))


class TestCrypto(TestCase):
    def test_valid_ecc(self):
        for i in range(100):
            e = get_ecc()
            assert len(e.raw_pubkey) == 64
            assert e.is_valid_key(e.raw_pubkey)
            assert e.is_valid_key(e.raw_pubkey, e.raw_privkey)

        pubkey = '\x00' * 64
        assert not e.is_valid_key(pubkey)

    def test_asymetric(self):
        bob = get_ecc('secret2')

        # enc / dec
        plaintext = "Hello Bob"
        ciphertext = crypto.encrypt(plaintext, bob.raw_pubkey)
        assert bob.decrypt(ciphertext) == plaintext

    def test_signature(self):
        bob = get_ecc('secret2')

        # sign
        message = crypto.sha3("Hello Alice")
        signature = bob.sign(message)

        # verify signature
        assert crypto.verify(bob.raw_pubkey, signature, message) is True
        assert crypto.ECCx(raw_pubkey=bob.raw_pubkey).verify(signature, message) is True

        # wrong signature
        message = crypto.sha3("Hello Alicf")
        assert crypto.ECCx(raw_pubkey=bob.raw_pubkey).verify(signature, message) is False
        assert crypto.verify(bob.raw_pubkey, signature, message) is False

    def test_recover(self):
        alice = get_ecc('secret1')
        message = crypto.sha3('hello bob')
        signature = alice.sign(message)
        assert len(signature) == 65
        assert crypto.verify(alice.raw_pubkey, signature, message) is True
        recovered_pubkey = crypto.ecdsa_recover(message, signature)
        assert len(recovered_pubkey) == 64
        assert alice.raw_pubkey == recovered_pubkey

    def test_get_ecdh_key(self):
        privkey = "332143e9629eedff7d142d741f896258f5a1bfab54dab2121d3ec5000093d74b".decode('hex')
        remote_pubkey = "f0d2b97981bd0d415a843b5dfe8ab77a30300daab3658c578f2340308a2da1a07f0821367332598b6aa4e180a41e92f4ebbae3518da847f0b1c0bbfe20bcf4e1".decode(
            'hex')

        agree_expected = "ee1418607c2fcfb57fda40380e885a707f49000a5dda056d828b7d9bd1f29a08".decode(
            'hex')

        e = crypto.ECCx(raw_privkey=privkey)
        agree = e.get_ecdh_key(remote_pubkey)
        assert agree == agree_expected

    def test_en_decrypt(self):
        alice = crypto.ECCx()
        bob = crypto.ECCx()
        msg = 'test'
        ciphertext = alice.encrypt(msg, bob.raw_pubkey)
        assert bob.decrypt(ciphertext) == msg

    def test_en_decrypt_shared_mac_data(self):
        alice, bob = crypto.ECCx(), crypto.ECCx()
        ciphertext = alice.encrypt('test', bob.raw_pubkey, shared_mac_data='shared mac data')
        assert bob.decrypt(ciphertext, shared_mac_data='shared mac data') == 'test'

    def test_en_decrypt_shared_mac_data_fail(self):
        with self.assertRaises(crypto.ECIESDecryptionError):
            alice, bob = crypto.ECCx(), crypto.ECCx()
            ciphertext = alice.encrypt('test', bob.raw_pubkey, shared_mac_data='shared mac data')
            bob.decrypt(ciphertext, shared_mac_data='wrong')

    def test_privtopub(self):
        priv = crypto.mk_privkey('test')
        pub = crypto.privtopub(priv)
        pub2 = crypto.ECCx(raw_privkey=priv).raw_pubkey
        assert pub == pub2


def recover_1kb(times=1000):
    alice = get_ecc('secret1')
    message = ''.join(chr(random.randrange(0, 256)) for i in range(1024))
    message = crypto.sha3(message)
    signature = alice.sign(message)
    for i in range(times):
        recovered_pubkey = crypto.ecdsa_recover(message, signature)
    assert recovered_pubkey == alice.raw_pubkey


def test_recover2():
    recover_1kb(times=1)


if __name__ == '__main__':
    import time

    st = time.time()
    times = 100
    recover_1kb(times=times)
    print 'took %.5f per recovery' % ((time.time() - st) / times)
