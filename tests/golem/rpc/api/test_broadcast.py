import binascii

from freezegun import freeze_time
import golem_messages.exceptions

from golem import model
from golem import testutils
from golem.rpc.api import broadcast_ as api_broadcast


class BroadcastTestBase(testutils.DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.timestamp = 1582813813
        self.broadcast_type = 1
        self.data_hex = '302e3233'
        self.hash_ = '20cd626884c83455ab59fbfbfe2944fa6e187c20'
        self.signature_hex = '7cf206f88696700f1a6f87c4a99a4bf11e8526a860f2a9d32345a3c1f9a95d985e1878ef60495e8deca4032d5622ffa02a3f059248084d07aee4dd4effead64500'  # noqa pylint: disable=line-too-long
        self.query = model.Broadcast.select().where(
            model.Broadcast.timestamp == self.timestamp,
            model.Broadcast.broadcast_type == self.broadcast_type,
            model.Broadcast.data == b'0.23',
            model.Broadcast.signature == b'|\xf2\x06\xf8\x86\x96p\x0f\x1ao\x87\xc4\xa9\x9aK\xf1\x1e\x85&\xa8`\xf2\xa9\xd3#E\xa3\xc1\xf9\xa9]\x98^\x18x\xef`I^\x8d\xec\xa4\x03-V"\xff\xa0*?\x05\x92H\x08M\x07\xae\xe4\xddN\xff\xea\xd6E\x00',  # noqa pylint: disable=line-too-long
        )


class HashTest(BroadcastTestBase):
    def test_basic(self):
        result = api_broadcast.hash_(
            timestamp=self.timestamp,
            broadcast_type=self.broadcast_type,
            data_hex=self.data_hex,
        )
        self.assertIsInstance(result, str)
        self.assertEqual(result, self.hash_)

    def test_string_arguments(self):
        # Useful when using with `golemcli debug rpc`
        result = api_broadcast.hash_(
            timestamp=str(self.timestamp),
            broadcast_type=str(self.broadcast_type),
            data_hex=self.data_hex,
        )
        self.assertIsInstance(result, str)
        self.assertEqual(result, self.hash_)


class PushTest(BroadcastTestBase):
    def test_basic(self):
        api_broadcast.push(
            timestamp=self.timestamp,
            broadcast_type=self.broadcast_type,
            data_hex=self.data_hex,
            signature_hex=self.signature_hex,
        )
        self.assertTrue(self.query.exists())

    def test_string_arguments(self):
        # Useful when using with `golemcli debug rpc`
        api_broadcast.push(
            timestamp=str(self.timestamp),
            broadcast_type=str(self.broadcast_type),
            data_hex=self.data_hex,
            signature_hex=self.signature_hex,
        )
        self.assertTrue(self.query.exists())

    def test_invalid_signature(self):
        with self.assertRaises(golem_messages.exceptions.InvalidSignature):
            api_broadcast.push(
                timestamp=str(self.timestamp),
                broadcast_type=str(self.broadcast_type),
                data_hex=self.data_hex,
                signature_hex='7cf206f88696700f1a6f87c4a99a4bf11e8526a860f2a9d32345a3c1f9a95d985e1878ef60495e8deca4032d5622ffa02a3f059248084d07aee4dd4effead64501',  # noqa pylint: disable=line-too-long
            )
        self.assertFalse(self.query.exists())

    def test_invalid_signature_invalid_hex(self):
        with self.assertRaises(binascii.Error):
            api_broadcast.push(
                timestamp=str(self.timestamp),
                broadcast_type=str(self.broadcast_type),
                data_hex=self.data_hex,
                signature_hex='bubliboo',
            )
        self.assertFalse(self.query.exists())


class ListTest(BroadcastTestBase):
    @freeze_time("2018-01-01 00:00:00")
    def test_basic(self):
        api_broadcast.push(
            timestamp=self.timestamp,
            broadcast_type=self.broadcast_type,
            data_hex=self.data_hex,
            signature_hex=self.signature_hex,
        )
        result = api_broadcast.list_()
        self.assertEqual(
            result,
            [
                {
                    'timestamp': self.timestamp,
                    'broadcast_type': self.broadcast_type,
                    'broadcast_type_name': 'Version',
                    'data_hex': self.data_hex,
                    'created_date': 1514764800,
                },
            ]
        )
