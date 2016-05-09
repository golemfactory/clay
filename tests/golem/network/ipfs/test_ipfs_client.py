import os
import unittest
import uuid
from types import FunctionType

from golem.network.ipfs.client import IPFSClient, parse_response_entry, StreamFileObject, parse_response, IPFSAddress
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


class TestIpfsClient(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        task_id = str(uuid.uuid4())

        self.node_name = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path, self.node_name)

        res_path = self.dir_manager.get_task_resource_dir(task_id)
        self.test_dir = os.path.join(res_path, 'test_dir')
        self.test_dir_file = os.path.join(self.test_dir, 'dir_file')

        if not os.path.isdir(self.test_dir):
            os.mkdir(self.test_dir)

        with open(self.test_dir_file, 'w') as f:
            f.write("test content")

    def testAdd(self):
        client = IPFSClient()
        client.add([self.test_dir_file])

    def testGetFile(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        tmp_filename = 'tmp_file'

        client.get_file(response[0]['Hash'],
                        filepath=self.test_dir,
                        filename=tmp_filename)

    def testPinAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response[0]['Hash'])

    def testPinRm(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response[0]['Hash'])
        client.pin_rm(response[0]['Hash'])


class TestParseResponseEntry(unittest.TestCase):
    def test(self):
        json_str = '{"a": [12, 1, 0]}'
        other_str = '{ Something ]'

        self.assertEqual(type(other_str), type(parse_response_entry(other_str)[0]))
        self.assertEqual(dict, type(parse_response_entry(json_str)[0]))


class TestParseResponse(unittest.TestCase):

    def test(self):
        valid_response = '[{"a":"b"}, {"b":1}]'
        other_response = 'Something else'

        response_obj = [[{u"a": u"b"}, {u"b": 1}]]
        other_obj = [['Something else']]
        parsed = parse_response(valid_response)[0]

        self.assertEqual(response_obj, parsed)
        self.assertEqual(other_obj, parse_response(other_response))


class MockIterator:
    def __init__(self, src, chunk):
        self.src = src
        self.len = len(src)
        self.chunk = chunk
        self.pos = 0

    def __iter__(self):
        return self

    def next(self):
        prev_pos = self.pos
        self.pos += self.chunk

        if prev_pos > self.len:
            raise StopIteration
        else:
            new_pos = max(prev_pos, self.len - self.pos)
            return self.src[prev_pos:new_pos]


class MockIterable:
    def __init__(self, src):
        self.iterator = None
        self.src = src

    def iter_content(self, chunk, *args):
        if not self.iterator:
            self.iterator = MockIterator(self.src, chunk)
        return self.iterator


class TestStreamFileObject(unittest.TestCase):

    def test(self):
        src = ''
        for _ in xrange(1, 100):
            src = str(uuid.uuid4())

        iterable = MockIterable(src)
        so = StreamFileObject(iterable)

        try:
            so.read(32)
        except StopIteration:
            pass


class TestIPFSClientMetaclass(unittest.TestCase):

    def test(self):
        client = IPFSClient()
        parent = super(IPFSClient, client)

        for name, attribute in client.__dict__.iteritems():
            if parent.__dict__.has_key(name):
                if type(attribute) == FunctionType and not name.startswith('_'):
                    assert client.__getattribute__(name) is not \
                           parent.__getattribute__(name)
                else:
                    assert client.__getattribute__(name) is \
                           parent.__getattribute__(name)


class TestChunkedHttpClient(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        self.node_name = str(uuid.uuid4())

        self.target_dir = os.path.join(self.path, str(uuid.uuid4()))
        self.test_dir = os.path.join(self.path, 'test_dir')
        self.test_dir_file_path = os.path.join(self.test_dir, 'test_dir_file')
        self.test_file_path = os.path.join(self.path, 'test_file')

        if not os.path.isdir(self.test_dir):
            os.mkdir(self.test_dir)
        if not os.path.isdir(self.target_dir):
            os.mkdir(self.target_dir)

        with open(self.test_file_path, 'w') as f:
            f.write("test content")

        with open(self.test_dir_file_path, 'w') as f:
            f.write("test content 2")

    def testGetFile(self):
        root_path = os.path.abspath(os.sep)
        client = IPFSClient()

        self.added_files = []
        self.added_files += client.add(self.test_dir_file_path)
        self.added_files += client.add(self.test_file_path)

        for added in self.added_files:
            name = added['Name']
            if name.startswith(root_path):
                target_filename = 'downloaded_file'

                result = client.get_file(added['Hash'],
                                         filepath=self.target_dir,
                                         filename=target_filename)

                filename, multihash = result[0]
                filepath = os.path.join(self.target_dir, filename)
                assert filename == target_filename
                assert os.path.exists(filepath)

                os.remove(filepath)

                result = client.get_file(added['Hash'],
                                         filepath=self.target_dir,
                                         filename=target_filename,
                                         compress=True,
                                         archive=True)

                filename, multihash = result[0]
                filepath = os.path.join(self.target_dir, filename)
                assert filename == target_filename
                assert os.path.exists(filepath)

    def testGet(self):
        client = IPFSClient()
        with self.assertRaises(NotImplementedError):
            client.get("-")

    def testWriteFile(self):
        client = IPFSClient()
        src = ''
        for _ in xrange(1, 100):
            src = str(uuid.uuid4())

        filename = str(uuid.uuid4())
        expected_path = os.path.join(self.test_dir, filename)

        iterable = MockIterable(src)
        client._client._write_file(iterable, self.test_dir,
                                   filename, str(uuid.uuid4()))

        assert os.path.exists(expected_path)


class TestIPFSAddress(unittest.TestCase):

    def testAllowedIPAddress(self):
        assert not IPFSAddress.allowed_ip_address('127.0.0.1')
        assert not IPFSAddress.allowed_ip_address('10.10.10.10')
        assert IPFSAddress.allowed_ip_address('8.8.8.8')

    def testBuildIPFSAddress(self):
        hash = 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        expected_ipv4 = '/ip4/127.0.0.1/tcp/4001/ipfs/' + hash
        expected_ipv6 = '/ip6/::1/tcp/14001/ipfs/' + hash

        ipv4 = str(IPFSAddress('127.0.0.1', hash))
        ipv6 = str(IPFSAddress('::1', hash, port=14001))

        assert ipv4 == expected_ipv4
        assert ipv6 == expected_ipv6

        expected_utp_ipv4 = '/ip4/0.0.0.0/udp/4002/utp/ipfs/' + hash

        utp_ipv4 = IPFSAddress('0.0.0.0', hash,
                               port=4002,
                               proto='udp',
                               encap_proto='utp')

        assert str(utp_ipv4) == expected_utp_ipv4

    def testParseIPFSAddress(self):
        ipfs_addr_str = '/ip4/127.0.0.1/tcp/4001/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        assert str(IPFSAddress.parse(ipfs_addr_str)) == ipfs_addr_str
        ipfs_addr_str_2 = '/ip4/127.0.0.1/udp/4002/utp/ipfs/QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        assert str(IPFSAddress.parse(ipfs_addr_str_2)) == ipfs_addr_str_2
