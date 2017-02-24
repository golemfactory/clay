import hashlib
import os
import unittest
import uuid
from types import FunctionType
from unittest import skipIf

from golem.network.ipfs.client import IPFSClient, IPFSAddress, ipfs_running
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


@skipIf(not ipfs_running(), "IPFS daemon isn't running")
class TestIpfsClient(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)

        task_id = str(uuid.uuid4())

        self.node_name = str(uuid.uuid4())
        self.dir_manager = DirManager(self.path)

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

        get_response = client.get_file(response['Hash'],
                                       filepath=self.test_dir,
                                       filename=tmp_filename)

        assert get_response['Name'] == os.path.join(self.test_dir, tmp_filename)
        assert get_response['Hash'] == response['Hash']

        tmp_file_path = os.path.join(self.test_dir, tmp_filename)

        assert os.stat(tmp_file_path).st_size == os.stat(self.test_dir_file).st_size
        assert md5sum(tmp_file_path) == md5sum(self.test_dir_file)

    def testPinAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)
        client.pin_add(response['Hash'])

    def testPinRm(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response['Hash'])
        client.pin_rm(response['Hash'])


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

    @skipIf(not ipfs_running(), "IPFS daemon isn't running")
    def testGetFile(self):
        root_path = os.path.abspath(os.sep)
        client = IPFSClient()

        self.added_files = [
            client.add(self.test_dir_file_path),
            client.add(self.test_file_path)
        ]
        target_filename = 'downloaded_file'

        for added in self.added_files:
            name = added['Name']
            if name.startswith(root_path) and 'Hash' in added:

                result = client.get_file(added['Hash'],
                                         filepath=self.target_dir,
                                         filename=target_filename)

                filename, _ = result[0]
                filepath = os.path.join(self.target_dir, filename)

                assert filename == target_filename
                assert os.path.exists(filepath)

                with self.assertRaises(Exception):
                    client.get_file(added['Hash'],
                                    filepath=self.target_dir,
                                    filename=target_filename,
                                    compress=False)

    def testGet(self):
        root_path = os.path.abspath(os.sep)
        client = IPFSClient()

        self.added_files = [
            client.add(self.test_dir_file_path),
            client.add(self.test_file_path)
        ]
        self.names = [added['Name'] for added in self.added_files]

        for added in self.added_files:
            name = added['Name']
            if name.startswith(root_path) and 'Hash' in added:

                result = client.get_file(added['Hash'],
                                         filepath=self.target_dir)

                file_name, _ = result[0]
                file_path = os.path.join(self.target_dir, file_name)

                assert file_name in self.names
                assert os.path.exists(file_path)

    def testBuildOptions(self):
        from golem.resource.client import ClientError
        client = IPFSClient()
        client_options = {'options': {'option1': 1, 'option2': 'abcd', 'option3': None}}
        option = client.build_options("id", **client_options)
        print option
        assert option.client_id == client.CLIENT_ID
        assert option.version == client.VERSION
        with self.assertRaises(ClientError):
            option.get("Incorrect_id", client.VERSION, None)
        with self.assertRaises(ClientError):
            option.get(client.CLIENT_ID, client.VERSION + 1, None)
        assert option.get(client.CLIENT_ID, client.VERSION, 'option1') == 1
        assert option.get(client.CLIENT_ID, client.VERSION, 'option2') == "abcd"
        assert not option.get(client.CLIENT_ID, client.VERSION, 'option3')


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
