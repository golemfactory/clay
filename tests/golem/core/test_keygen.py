from unittest import TestCase

from golem.core.keysauth import mk_privkey, privtopub


def key_in_hex(key):
    return ':'.join(x.encode('hex') for x in key)


class TestKeygenHelper(TestCase):
    """First three test vectors from http://www.di-mgt.com.au/sha_testvectors.html"""
    def test_mk_privkey(self):
        key = key_in_hex(mk_privkey(str("")))
        self.assertEqual(key, "a7:ff:c6:f8:bf:1e:d7:66:51:c1:47:56:a0:61:d6:62:f5:80:ff:4d:e4:3b:49:fa:82:d8:0a:4b:80:f8:43:4a")

        key = key_in_hex(mk_privkey(str("abc")))
        self.assertEqual(key, "3a:98:5d:a7:4f:e2:25:b2:04:5c:17:2d:6b:d3:90:bd:85:5f:08:6e:3e:9d:52:5b:46:bf:e2:45:11:43:15:32")

        key = key_in_hex(mk_privkey(str("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")))
        self.assertEqual(key, "41:c0:db:a2:a9:d6:24:08:49:10:03:76:a8:23:5e:2c:82:e1:b9:99:8a:99:9e:21:db:32:dd:97:49:6d:33:76")

        key = key_in_hex(mk_privkey(str("ala")))
        self.assertEqual(key, "dd:8a:21:63:67:a5:61:6f:25:ce:f9:dc:48:ed:a8:6d:6e:a6:8c:b5:9f:9f:0d:f6:9a:f3:49:14:e3:ce:77:50")

        key = key_in_hex(mk_privkey(str("102")))
        self.assertEqual(key, "36:72:ce:6f:f4:6a:e7:4b:28:1f:cb:27:88:1a:ff:d1:8e:54:e3:ef:ac:c1:10:31:36:4b:69:41:6c:92:64:b1")

        key = key_in_hex(mk_privkey(str("-4")))
        self.assertEqual(key, "73:8d:11:18:1b:63:c5:15:90:e9:b6:c7:42:66:b8:03:09:4e:f0:54:36:74:8e:df:0b:26:5c:75:7d:77:a5:76")

        key = key_in_hex(mk_privkey(str("0.234")))
        self.assertEqual(key, "6f:ad:32:c1:06:f7:30:f4:b4:83:d2:d3:57:52:5d:63:79:b4:eb:ad:ae:1e:00:06:1a:95:ab:c5:b3:7a:e6:78")

    def test_privtopub(self):
        key = key_in_hex(privtopub(mk_privkey(str(""))))
        self.assertEqual(key, "c9:88:c2:98:ec:51:45:16:12:11:76:a5:11:7c:8a:4f:96:92:91:4b:0e:19:7d:2d:42:5d:73:3f:83:e4:1b:89:1e:d9:b8:24:59:32:8c:1a:b7:e3:c2:05:07:c8:6e:8b:ea:d9:32:0b:95:0c:56:56:09:f8:60:eb:b5:37:70:88")

        key = key_in_hex(privtopub(mk_privkey(str("ala"))))
        self.assertEqual(key, "88:aa:ea:31:f4:2c:37:a4:29:ba:5a:7a:52:2d:0a:00:6f:b6:81:ce:20:cd:fc:85:2f:61:8e:e6:80:22:8a:2e:d0:ae:aa:72:e2:9c:05:9d:58:9e:d0:8c:64:25:c3:d7:40:05:68:60:f3:69:c8:be:0e:3c:8b:69:70:d1:7a:b4")

        key = key_in_hex(privtopub(mk_privkey(str("102"))))
        self.assertEqual(key, "78:b9:32:5c:46:6c:77:f4:ac:35:0f:ee:37:75:03:e7:0d:49:d2:92:4a:54:bd:eb:21:4c:3c:6f:da:d4:e2:c8:0f:16:0b:69:f2:3d:c6:0e:1e:da:4b:30:52:9e:a1:11:13:b7:a5:c0:33:1c:87:fa:a0:7c:29:84:fa:9e:ca:aa")

        key = key_in_hex(privtopub(mk_privkey(str("-4"))))
        self.assertEqual(key, "9d:36:a5:fe:87:b2:8a:af:88:67:a4:31:67:2a:4f:f3:37:f7:51:ab:74:e8:c9:bf:9b:cb:d5:ee:33:54:ab:91:74:90:89:aa:47:25:b8:1b:cd:97:d2:e8:1d:ae:3d:74:e1:e0:18:44:38:74:98:c7:7d:9f:0d:9b:36:b5:c4:c1")

        key = key_in_hex(privtopub(mk_privkey(str("0.234"))))
        self.assertEqual(key, "2c:b3:35:f6:f2:a5:26:2c:ba:b5:85:10:47:37:d6:b1:56:fb:6e:20:73:f1:91:e4:35:b6:34:0f:d6:90:3b:d5:d3:f1:91:35:db:08:28:43:88:1e:40:96:d7:5d:b4:c3:54:84:a5:fd:8a:cc:30:85:ca:08:84:f5:a4:5c:fa:64")
