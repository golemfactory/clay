import hashlib
import os
import unittest
import uuid
from unittest import skipIf

from golem.network.ipfs.client import IPFSClient, IPFSAddress, ipfs_running
from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture


@skipIf(not ipfs_running(), "IPFS daemon isn't running")
class TestIPFSClient(TestDirFixture):

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

        self._write_test_file(1)

    def testAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])
        assert response['Name']
        assert response['Hash']

    def testGet(self):
        self._write_test_file(102400)

        client = IPFSClient()
        response = client.add([self.test_dir_file])

        client.get(response['Hash'],
                   filepath=self.test_dir)

        tmp_file_path = os.path.join(self.test_dir, response['Hash'])

        assert os.stat(tmp_file_path).st_size == os.stat(self.test_dir_file).st_size
        assert self._md5sum(tmp_file_path) == self._md5sum(self.test_dir_file)

    def testGetFile(self):
        self._write_test_file(102400)

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
        assert self._md5sum(tmp_file_path) == self._md5sum(self.test_dir_file)

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

    def _write_test_file(self, n_entries):
        with open(self.test_dir_file, 'w') as f:
            for i in xrange(0, n_entries):
                f.write(str(uuid.uuid4()) + "\n")
                f.flush()

    @staticmethod
    def _md5sum(file_name):
        hash_md5 = hashlib.md5()
        with open(file_name, "rb") as f:
            for chunk in iter(lambda: f.read(1024), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()


class TestIPFSAddress(unittest.TestCase):

    def testAllowedIPAddress(self):
        assert not IPFSAddress.allowed_ip_address('127.0.0.1')
        assert not IPFSAddress.allowed_ip_address('10.10.10.10')
        assert IPFSAddress.allowed_ip_address('8.8.8.8')

    def testBuildIPFSAddress(self):
        hash = 'QmS8Kx4wTTH7ASvjhqLj12evmHvuqK42LDiHa3tLn24VvB'
        expected_ipv4 = '/ip4/127.0.0.1/tcp/4001/ipfs/{}'.format(hash)
        expected_ipv6 = '/ip6/::1/tcp/14001/ipfs/{}'.format(hash)

        ipv4 = str(IPFSAddress('127.0.0.1', hash))
        ipv6 = str(IPFSAddress('::1', hash, port=14001))

        assert ipv4 == expected_ipv4
        assert ipv6 == expected_ipv6

        expected_utp_ipv4 = '/ip4/0.0.0.0/udp/4002/utp/ipfs/{}'.format(hash)

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
