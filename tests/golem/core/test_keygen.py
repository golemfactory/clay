from unittest import TestCase

from devp2p.crypto import mk_privkey, privtopub


def key_in_hex(key):
    return ':'.join(x.encode('hex') for x in key)


class TestKeygenHelper(TestCase):
    def test_mk_privkey(self):
        key = key_in_hex(mk_privkey(str("")))
        self.assertEqual(key, "c5:d2:46:01:86:f7:23:3c:92:7e:7d:b2:dc:c7:03:c0:e5:00:b6:53:ca:82:27:3b:7b:fa:d8:04:5d:85:a4:70")
        key = key_in_hex(mk_privkey(str("ala")))
        self.assertEqual(key, "f5:e0:69:54:a3:a7:c1:cc:ae:d8:67:5b:3f:b4:29:e2:3a:83:9b:5b:40:6a:72:43:2b:d6:53:2d:cd:40:0d:18")
        key = key_in_hex(mk_privkey(str("102")))
        self.assertEqual(key, "2a:90:63:ed:52:b7:d4:17:e4:41:f3:78:32:53:59:c9:ce:27:4f:5d:6c:3e:cf:11:b7:d4:2f:24:b9:c9:0b:7f")
        key = key_in_hex(mk_privkey(str("-4")))
        self.assertEqual(key, "70:25:25:ac:62:9b:e2:23:a9:df:40:af:dd:83:ad:49:12:68:dd:60:af:4e:67:03:d2:f7:1e:f8:a0:b5:24:08")
        key = key_in_hex(mk_privkey(str("0.234")))
        self.assertEqual(key, "2e:ac:65:5c:86:35:49:07:b5:a7:97:06:be:28:03:d4:49:fa:3d:a2:c6:6e:e9:cc:0e:e0:e1:b0:0e:69:f9:da")

    def test_privtopub(self):
        key = key_in_hex(privtopub(mk_privkey(str(""))))
        self.assertEqual(key, "a6:3a:07:e8:88:06:1e:c9:e8:b6:4a:3d:c2:93:78:05:c7:60:89:af:36:45:93:05:92:03:73:cd:98:a9:f4:ce:15:c2:7d:bb:e6:09:28:16:1e:b6:2a:e1:9f:94:ea:48:f3:99:ce:85:e6:db:69:85:20:f3:bc:d4:a9:25:71:57")
        key = key_in_hex(privtopub(mk_privkey(str("ala"))))
        self.assertEqual(key, "17:c5:52:9f:c8:ee:fc:86:89:e4:66:b9:3d:b2:b8:45:13:db:56:81:3c:e9:a3:40:42:87:63:38:14:d8:b4:99:fa:4b:66:7b:b3:39:d6:6d:1c:d7:24:f4:a3:38:5e:cb:db:8c:50:38:f5:e0:4b:fc:a6:e6:b4:02:6f:d7:b9:db")
        key = key_in_hex(privtopub(mk_privkey(str("102"))))
        self.assertEqual(key, "1e:c2:3d:1a:c5:18:01:57:77:e4:60:0b:c6:17:14:4b:0d:04:f3:d8:f4:f6:9c:94:5d:55:3a:40:36:2a:66:1a:5d:ee:4f:cf:75:cf:a2:74:f8:be:e9:84:e8:d5:17:ef:3d:23:fa:6a:03:e2:9b:48:e4:30:dc:7c:98:3b:2a:89")
        key = key_in_hex(privtopub(mk_privkey(str("-4"))))
        self.assertEqual(key, "ea:f8:b0:4c:53:10:fd:1d:9d:61:44:03:d3:45:07:78:f7:bc:2e:14:10:91:49:94:06:96:3e:02:46:0a:62:ed:b8:b2:5f:c3:9a:18:fc:84:04:51:fb:eb:83:cf:4a:9d:15:70:f1:58:ab:4d:54:1d:72:5b:c1:35:ed:5e:8c:84")
        key = key_in_hex(privtopub(mk_privkey(str("0.234"))))
        self.assertEqual(key, "20:c9:df:38:0a:d7:73:38:a5:17:b6:df:72:5d:04:e4:6e:aa:6d:52:e8:33:85:df:4a:e2:49:dc:db:50:be:bc:11:e5:e4:fd:30:39:49:e2:ca:a5:5a:bf:62:ff:f7:94:5a:3d:71:0b:8e:d1:cd:95:57:98:b5:71:e5:98:cc:f9")
