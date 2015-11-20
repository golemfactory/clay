import unittest
import sys
import os

sys.path.append(os.environ.get('GOLEM'))

from golem.network.adapter.sftpadapter import SFTPAdapter, SFTPHostInfo, SFTPResourceInfo
from golem.network.adapter.adapter import ClosedAdapterError

#To pass tests fill-in two files "test" and "test2"

class TestSFTPAdapters(unittest.TestCase):
    def test_connect_password(self):
        sftp_adapter = SFTPAdapter()
        with open('test', 'r') as f:
            address = f.readline()[:-1]
            username = f.readline()[:-1]
            password = f.readline()[:-1]
        sftp_host_info = SFTPHostInfo(address, username=username, password=password)
        self.assertTrue(sftp_adapter.connect(sftp_host_info))
        self.assertTrue(sftp_adapter.close())
        self.assertFalse(sftp_adapter.close())
        sftp_host_info.password = 'bla'
        self.assertFalse(sftp_adapter.connect(sftp_host_info))
        self.assertFalse(sftp_adapter.close())

    def test_connect_key(self):
        sftp_adapter = SFTPAdapter()
        with open('test2', 'r') as f:
            address = f.readline()[:-1]
            username = f.readline()[:-1]
            private_key = f.readline()[:-1]
            private_key_pass = f.readline()[:-1]
        sftp_host_info = SFTPHostInfo(address, username=username, private_key=private_key,
                                      private_key_pass=private_key_pass)
        print private_key_pass
        print private_key
        self.assertTrue(sftp_adapter.connect(sftp_host_info))

    def test_resource(self):
        sftp_adapter = SFTPAdapter()
        with open('test', 'r') as f:
            address = f.readline()[:-1]
            username = f.readline()[:-1]
            password = f.readline()[:-1]
            resource_name = f.readline()[:-1]
            resource_dir = f.readline()[:-1]
        sftp_host_info = SFTPHostInfo(address, username=username, password=password)
        sftp_adapter.connect(sftp_host_info)
        resource_info = SFTPResourceInfo(resource_name, resource_dir)
        sftp_adapter.get_resource(resource_info)
        self.assertTrue(os.path.isfile(resource_name))
        sftp_adapter.send_resource(resource_name)
        sftp_adapter.close()
        with self.assertRaises(ClosedAdapterError):
            sftp_adapter.get_resource(resource_info)

if __name__ == '__main__':
    unittest.main()
