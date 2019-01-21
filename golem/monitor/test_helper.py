import asyncio
from unittest import mock, TestCase
from uuid import uuid4

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG
from golem.tools.os_info import OSInfo


def meta_data():
    client_mock = mock.MagicMock()
    client_mock.cliid = str(uuid4())
    client_mock.sessid = str(uuid4())
    client_mock.config_desc = ClientConfigDescriptor()
    client_mock.mainnet = False
    os_info = OSInfo(
        'linux',
        'Linux',
        '1',
        '1.2.3'
    )
    return NodeMetadataModel(client_mock, os_info, 'app_version')


class MonitorTestBaseClass(TestCase):
    def setUp(self):
        self.monitor = SystemMonitor(meta_data(), MONITOR_CONFIG)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        asyncio.set_event_loop(None)
