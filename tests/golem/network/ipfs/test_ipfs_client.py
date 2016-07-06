import hashlib
import os
import unittest
import uuid
from types import FunctionType

from golem.network.ipfs.client import IPFSClient, parse_response_entry, parse_response, IPFSAddress
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


def first_response_hash(response):
    if response:
        for item in response:
            if isinstance(item, dict):
                if 'Hash' in item:
                    return item['Hash']
            else:
                result = first_response_hash(item)
                if result:
                    return result
    return None


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
        def md5sum(file_name):
            hash_md5 = hashlib.md5()
            with open(file_name, "rb") as f:
                for chunk in iter(lambda: f.read(1024), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        os.remove(self.test_dir_file)
        with open(self.test_dir_file, 'w') as f:
            for i in xrange(0, 102400):
                f.write(str(uuid.uuid4()) + "\n")
                f.flush()

        client = IPFSClient()
        response = client.add([self.test_dir_file])
        assert response

        tmp_filename = 'tmp_file'

        assert client.get_file(first_response_hash(response),
                               filepath=self.test_dir,
                               filename=tmp_filename)

        tmp_file_path = os.path.join(self.test_dir, tmp_filename)

        assert os.stat(tmp_file_path).st_size == os.stat(self.test_dir_file).st_size
        assert md5sum(tmp_file_path) == md5sum(self.test_dir_file)

    def testPinAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)
        client.pin_add(first_response_hash(response))

    def testPinRm(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(first_response_hash(response))
        client.pin_rm(first_response_hash(response))


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


class TestIPFSClientMetaclass(unittest.TestCase):

    def test(self):
        client = IPFSClient()
        parent = super(IPFSClient, client)

        for name, attribute in client.__dict__.iteritems():
            if name in parent.__dict__:
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

        for entries in self.added_files:
            for added in entries:
                name = added['Name']
                if name.startswith(root_path) and 'Hash' in added:
                    target_filename = 'downloaded_file'

                    result = client.get_file(added['Hash'],
                                             filepath=self.target_dir,
                                             filename=target_filename)

                    filename, multihash = result[0]
                    filepath = os.path.join(self.target_dir, filename)

                    assert filename == target_filename
                    assert os.path.exists(filepath)

                    with self.assertRaises(Exception):
                        client.get_file(added['Hash'],
                                        filepath=self.target_dir,
                                        filename=target_filename,
                                        compress=False)

    def testGet(self):
        client = IPFSClient()
        with self.assertRaises(NotImplementedError):
            client.get("-")


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
