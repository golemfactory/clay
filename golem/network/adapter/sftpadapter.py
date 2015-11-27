import pysftp
import logging
import os

from adapter import Adapter, ClosedAdapterError
from golem.core.common import is_windows

logger = logging.getLogger(__name__)


class SFTPHostInfo(object):
    def __init__(self, address, port=22, username=None, password=None, private_key=None, private_key_pass=None):
        """ All information about SFTP connection
        :param str address: host address or name
        :param int port: *Default: 22* The SSH port of remote machine
        :param str|None username: username on host
        :param password: *Default: None* password to host
        :param str|obj|None private_key: *Default: None* path to private key file or paramiko.AgentKey
        :param str|None private_key_pass: *Default: None* password to use if private_key is encrypted
        :return: None
        """
        self.address = address
        self.port = port
        self.username = username
        self.password = password
        self.private_key = private_key
        self.private_key_pass = private_key_pass


class SFTPResourceInfo(object):
    """ Information about file that can be receive from sftp connection"""
    def __init__(self, name, path=""):
        """
        :param str name: file name
        :param str|None path: *Default: None* path to file
        :return: None
        """
        self.name = name
        self.path = path

    def to_file(self):
        """
        Translate resource info to remote file path
        :return: str full name of the resource to receive with sftp connection
        """
        file_to_get = os.path.normpath(os.path.join(self.path, self.name))
        if is_windows():
            file_to_get = file_to_get.replace('\\', '/')
        return file_to_get


class SFTPAdapter(Adapter):
    """ Golem SFTP network adapter """
    def __init__(self):
        self.opened = False
        self.sftp = None

    def connect(self, host_info, **kwargs):
        """ Connect to host specified in host_info
        :param SFTPHostInfo host_info:
            All information needed for connection
        :return: bool return true true if connection was opened
        """
        assert isinstance(host_info, SFTPHostInfo)
        if self.opened:
            self.close()
        try:
            self.sftp = pysftp.Connection(host_info.address, port=host_info.port, username=host_info.username,
                                          password=host_info.password, private_key=host_info.private_key,
                                          private_key_pass=host_info.private_key_pass)
            self.opened = True
        except Exception as ex:
            logger.error("Can't connect to {}: {}".format(host_info.address, ex))
        return self.opened

    def send_resource(self, resource, **kwargs):
        """
        Copies a file :resource: between local host nad remote host
        :param str resource: file to send to remote host
        :return None:
        """
        if not self.opened or self.sftp is None:
            raise ClosedAdapterError
        self.sftp.put(resource)

    def get_resource(self, resource_info, **kwargs):
        """
        Copies a file described in resource_info between remote host and local host
        :param SFTPResourceInfo  resource_info:
        :return None:
        """
        assert isinstance(resource_info, SFTPResourceInfo)

        if not self.opened or self.sftp is None:
            raise ClosedAdapterError
        file_to_get = resource_info.to_file()
        self.sftp.get(file_to_get)

    def close(self, *kwargs):
        """
        Closes the connect
        :return bool: Return True if connection was closed
        """
        if self.sftp and self.opened:
            self.sftp.close()
            self.opened = False
            return True
        else:
            self.opened = False
            return False
