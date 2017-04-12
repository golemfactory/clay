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
#!/usr/bin/python
CIPHERNAMES = set(('aes-128-ctr',))
import warnings
import os
import sys
if sys.platform not in ('darwin',):
    import pyelliptic
else:
    # FIX PATH ON OS X ()
    # https://github.com/yann2192/pyelliptic/issues/11
    _openssl_lib_paths = ['/usr/local/Cellar/openssl/']
    for p in _openssl_lib_paths:
        if os.path.exists(p):
            p = os.path.join(p, os.listdir(p)[-1], 'lib')
            os.environ['DYLD_LIBRARY_PATH'] = p
            import pyelliptic
            if CIPHERNAMES.issubset(set(pyelliptic.Cipher.get_all_cipher())):
                break
if 'pyelliptic' not in dir() or not CIPHERNAMES.issubset(set(pyelliptic.Cipher.get_all_cipher())):
    print 'required ciphers %r not available in openssl library' % CIPHERNAMES
    if sys.platform == 'darwin':
        print 'use homebrew or macports to install newer openssl'
        print '> brew install openssl / > sudo port install openssl'
    sys.exit(1)

import bitcoin
from Crypto.Hash import keccak
sha3_256 = lambda x: keccak.new(digest_bits=256, data=x)
from hashlib import sha256
import struct
from secp256k1 import PrivateKey, PublicKey, ALL_FLAGS


hmac_sha256 = pyelliptic.hmac_sha256


class ECIESDecryptionError(RuntimeError):
    pass


class ECCx(pyelliptic.ECC):

    """
    Modified to work with raw_pubkey format used in RLPx
    and binding default curve and cipher
    """
    ecies_ciphername = 'aes-128-ctr'
    curve = 'secp256k1'
    ecies_encrypt_overhead_length = 113

    def __init__(self, raw_pubkey=None, raw_privkey=None):
        if raw_privkey:
            assert not raw_pubkey
            raw_pubkey = privtopub(raw_privkey)
        if raw_pubkey:
            assert len(raw_pubkey) == 64
            _, pubkey_x, pubkey_y, _ = self._decode_pubkey(raw_pubkey)
        else:
            pubkey_x, pubkey_y = None, None
        while True:
            pyelliptic.ECC.__init__(self, pubkey_x=pubkey_x, pubkey_y=pubkey_y,
                                    raw_privkey=raw_privkey, curve=self.curve)
            try:
                if self.raw_privkey:
                    bitcoin.get_privkey_format(self.raw_privkey)  # failed for some keys
                valid_priv_key = True
            except AssertionError:
                valid_priv_key = False
            if len(self.raw_pubkey) == 64 and valid_priv_key:
                break
            elif raw_privkey or raw_pubkey:
                raise Exception('invalid priv or pubkey')

        assert len(self.raw_pubkey) == 64

    @property
    def raw_pubkey(self):
        return self.pubkey_x + self.pubkey_y

    @classmethod
    def _decode_pubkey(cls, raw_pubkey):
        assert len(raw_pubkey) == 64
        pubkey_x = raw_pubkey[:32]
        pubkey_y = raw_pubkey[32:]
        return cls.curve, pubkey_x, pubkey_y, 64

    def get_ecdh_key(self, raw_pubkey):
        "Compute public key with the local private key and returns a 256bits shared key"
        _, pubkey_x, pubkey_y, _ = self._decode_pubkey(raw_pubkey)
        key = self.raw_get_ecdh_key(pubkey_x, pubkey_y)
        assert len(key) == 32
        return key

    @property
    def raw_privkey(self):
        return self.privkey

    def is_valid_key(self, raw_pubkey, raw_privkey=None):
        try:
            assert len(raw_pubkey) == 64
            failed = bool(self.raw_check_key(raw_privkey, raw_pubkey[:32], raw_pubkey[32:]))
        except (AssertionError, Exception):
            failed = True
        return not failed

    @classmethod
    def ecies_encrypt(cls, data, raw_pubkey, shared_mac_data=''):
        """
        ECIES Encrypt, where P = recipient public key is:
        1) generate r = random value
        2) generate shared-secret = kdf( ecdhAgree(r, P) )
        3) generate R = rG [same op as generating a public key]
        4) send 0x04 || R || AsymmetricEncrypt(shared-secret, plaintext) || tag


        currently used by go:
        ECIES_AES128_SHA256 = &ECIESParams{
            Hash: sha256.New,
            hashAlgo: crypto.SHA256,
            Cipher: aes.NewCipher,
            BlockSize: aes.BlockSize,
            KeyLen: 16,
            }

        """
        # 1) generate r = random value
        ephem = ECCx()

        # 2) generate shared-secret = kdf( ecdhAgree(r, P) )
        key_material = ephem.raw_get_ecdh_key(pubkey_x=raw_pubkey[:32], pubkey_y=raw_pubkey[32:])
        assert len(key_material) == 32
        key = eciesKDF(key_material, 32)
        assert len(key) == 32
        key_enc, key_mac = key[:16], key[16:]

        key_mac = sha256(key_mac).digest()  # !!!
        assert len(key_mac) == 32
        # 3) generate R = rG [same op as generating a public key]
        ephem_pubkey = ephem.raw_pubkey

        # encrypt
        iv = pyelliptic.Cipher.gen_IV(cls.ecies_ciphername)
        assert len(iv) == 16
        ctx = pyelliptic.Cipher(key_enc, iv, 1, cls.ecies_ciphername)
        ciphertext = ctx.ciphering(data)
        assert len(ciphertext) == len(data)

        # 4) send 0x04 || R || AsymmetricEncrypt(shared-secret, plaintext) || tag
        msg = chr(0x04) + ephem_pubkey + iv + ciphertext

        # the MAC of a message (called the tag) as per SEC 1, 3.5.
        tag = hmac_sha256(key_mac, msg[1 + 64:] + shared_mac_data)
        assert len(tag) == 32
        msg += tag

        assert len(msg) == 1 + 64 + 16 + 32 + len(data) == 113 + len(data)
        assert len(msg) - cls.ecies_encrypt_overhead_length == len(data)
        return msg

    def ecies_decrypt(self, data, shared_mac_data=''):
        """
        Decrypt data with ECIES method using the local private key

        ECIES Decrypt (performed by recipient):
        1) generate shared-secret = kdf( ecdhAgree(myPrivKey, msg[1:65]) )
        2) verify tag
        3) decrypt

        ecdhAgree(r, recipientPublic) == ecdhAgree(recipientPrivate, R)
        [where R = r*G, and recipientPublic = recipientPrivate*G]

        """
        if data[0] != chr(0x04):
            raise ECIESDecryptionError("wrong ecies header")

        #  1) generate shared-secret = kdf( ecdhAgree(myPrivKey, msg[1:65]) )
        _shared = data[1:1 + 64]
        # FIXME, check that _shared_pub is a valid one (on curve)

        key_material = self.raw_get_ecdh_key(pubkey_x=_shared[:32], pubkey_y=_shared[32:])
        assert len(key_material) == 32
        key = eciesKDF(key_material, 32)
        assert len(key) == 32
        key_enc, key_mac = key[:16], key[16:]

        key_mac = sha256(key_mac).digest()
        assert len(key_mac) == 32

        tag = data[-32:]
        assert len(tag) == 32

        # 2) verify tag
        if not pyelliptic.equals(hmac_sha256(key_mac, data[1 + 64:- 32] + shared_mac_data), tag):
            raise ECIESDecryptionError("Fail to verify data")

        # 3) decrypt
        blocksize = pyelliptic.OpenSSL.get_cipher(self.ecies_ciphername).get_blocksize()
        iv = data[1 + 64:1 + 64 + blocksize]
        assert len(iv) == 16
        ciphertext = data[1 + 64 + blocksize:- 32]
        assert 1 + len(_shared) + len(iv) + len(ciphertext) + len(tag) == len(data)
        ctx = pyelliptic.Cipher(key_enc, iv, 0, self.ecies_ciphername)
        return ctx.ciphering(ciphertext)

    encrypt = ecies_encrypt
    decrypt = ecies_decrypt

    def sign(self, data):
        signature = ecdsa_sign(data, self.raw_privkey)
        assert len(signature) == 65
        return signature

    def verify(self, signature, message):
        assert len(signature) == 65
        return ecdsa_verify(self.raw_pubkey, signature, message)


def lzpad32(x):
    return '\x00' * (32 - len(x)) + x


def _encode_sig(v, r, s):
    assert isinstance(v, (int, long))
    assert v in (27, 28)
    vb, rb, sb = chr(v - 27), bitcoin.encode(r, 256), bitcoin.encode(s, 256)
    return lzpad32(rb) + lzpad32(sb) + vb


def _decode_sig(sig):
    return ord(sig[64]) + 27, bitcoin.decode(sig[0:32], 256), bitcoin.decode(sig[32:64], 256)


from secp256k1 import lib
ctx = lib.secp256k1_context_create(ALL_FLAGS)


def ecdsa_verify(pubkey, signature, message):
    assert len(signature) == 65
    assert len(pubkey) == 64
    pk = PublicKey('\04' + pubkey, raw=True, ctx=ctx)
    return pk.ecdsa_verify(
        message,
        pk.ecdsa_recoverable_convert(
            pk.ecdsa_recoverable_deserialize(
                signature[:64],
                ord(signature[64]))),
        raw=True
    )
verify = ecdsa_verify


def ecdsa_sign(msghash, privkey):
    assert len(msghash) == 32
    pk = PrivateKey(privkey, raw=True, ctx=ctx)
    signature = pk.ecdsa_recoverable_serialize(
        pk.ecdsa_sign_recoverable(
            msghash, raw=True))
    new = signature[0] + chr(signature[1])
    return new
sign = ecdsa_sign


def ecdsa_recover(message, signature):
    assert len(signature) == 65
    pk = PublicKey(flags=ALL_FLAGS, ctx=ctx)
    pk.public_key = pk.ecdsa_recover(
        message,
        pk.ecdsa_recoverable_deserialize(
            signature[:64],
            ord(signature[64])),
        raw=True
    )
    return pk.serialize(compressed=False)[1:]
recover = ecdsa_recover


def sha3(seed):
    return sha3_256(seed).digest()


def mk_privkey(seed):
    return sha3(seed)


def privtopub(raw_privkey):
    raw_pubkey = bitcoin.encode_pubkey(bitcoin.privtopub(raw_privkey), 'bin_electrum')
    assert len(raw_pubkey) == 64
    return raw_pubkey


def encrypt(data, raw_pubkey):
    """
    Encrypt data with ECIES method using the public key of the recipient.
    """
    assert len(raw_pubkey) == 64, 'invalid pubkey of len {}'.format(len(raw_pubkey))
    return ECCx.encrypt(data, raw_pubkey)


def eciesKDF(key_material, key_len):
    """
    interop w/go ecies implementation

    for sha3, blocksize is 136 bytes
    for sha256, blocksize is 64 bytes

    NIST SP 800-56a Concatenation Key Derivation Function (see section 5.8.1).
    """
    s1 = ""
    key = ""
    hash_blocksize = 64
    reps = ((key_len + 7) * 8) / (hash_blocksize * 8)
    counter = 0
    while counter <= reps:
        counter += 1
        ctx = sha256()
        ctx.update(struct.pack('>I', counter))
        ctx.update(key_material)
        ctx.update(s1)
        key += ctx.digest()
    return key[:key_len]
