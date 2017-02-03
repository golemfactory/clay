import mock
import random
from unittest import TestCase

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG

class TestSystemMonitor(TestCase):
    def test_monitor_messages(self):
        nmm = NodeMetadataModel("CLIID", "SESSID", "win32", "1.3", "Random description\n\t with additional data",
                                ClientConfigDescriptor())
        m = MONITOR_CONFIG
        m['HOST'] = "http://localhost/88881"
        monitor = SystemMonitor(nmm, m)
        monitor.start()
        monitor.on_login()

        monitor.on_payment(addr="some address", value=30139019301)
        monitor.on_income("different address", 319031904194810)
        monitor.on_peer_snapshot([{"node_id": "firt node", "port": 19301},
                                  {"node_id": "second node", "port": 3193}])
        ccd = ClientConfigDescriptor()
        ccd.node_name = "new node name"
        nmm = NodeMetadataModel("CLIID", "SESSID", "win32", "1.3", "Random description\n\t with additional data",
                                ccd)
        monitor.on_config_update(nmm)
        monitor.on_logout()
        monitor.shut_down()

    def test_protocol_versions(self):
        """Test wether correct protocol versions were sent."""
        from golem.network.p2p.peersession import P2P_PROTOCOL_ID
        from golem.task.tasksession import TASK_PROTOCOL_ID
        monitor = SystemMonitor(NodeMetadataModel("CLIID", "SESSID", "hackix", "3.1337", "Descr", ClientConfigDescriptor()), MONITOR_CONFIG)

        def check(f, msg_type):
            with mock.patch('golem.monitor.monitor.SenderThread.send') as mock_send:
                f()
                self.assertEquals(mock_send.call_count, 1)
                result = mock_send.call_args[0][0].dict_repr()
                for key in ('cliid', 'sessid', 'timestamp', 'metadata'):
                    del result[key]
                expected_d = {
                    'type': msg_type,
                    'protocol_versions': {
                        'monitor': MONITOR_CONFIG['PROTO_VERSION'],
                        'p2p': P2P_PROTOCOL_ID,
                        'task': TASK_PROTOCOL_ID,
                    },
                }

        check(monitor.on_login, "Login")
        check(monitor.on_logout, "Logout")
