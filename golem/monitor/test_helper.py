import sys
from unittest import mock, TestCase
from uuid import uuid4

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG


def meta_data():
    client_mock = mock.MagicMock()
    client_mock.session_id = 'sessid'
    client_mock.config_desc = ClientConfigDescriptor()
    client_mock.mainnet = False
    return NodeMetadataModel(client_mock, sys.platform, 'app_version')


class MonitorTestBaseClass(TestCase):
    def setUp(self):
        sign_mock = mock.MagicMock()
        sign_mock.public_key = b''
        sign_mock.sign.return_value = b''
        self.monitor = SystemMonitor(meta_data(), MONITOR_CONFIG, sign_mock)
