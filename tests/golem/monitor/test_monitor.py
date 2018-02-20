import random
from unittest import TestCase
from unittest import mock

import requests

from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor, SenderThread
from golem.monitorconfig import MONITOR_CONFIG
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats, \
    EMPTY_FINISHED_SUMMARY


class TestSystemMonitor(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = (
        "golem/monitor/monitor.py",
    )

    def setUp(self):
        random.seed()

    @staticmethod
    def test_monitor_messages():
        nmm = NodeMetadataModel("CLIID", "SESSID", "win32", "1.3",
                                ClientConfigDescriptor())
        m = MONITOR_CONFIG.copy()
        m['HOST'] = "http://localhost/88881"
        monitor = SystemMonitor(nmm, m)
        monitor.start()
        monitor.on_login()

        monitor.on_payment(addr="some address", value=30139019301)
        monitor.on_income("different address", 319031904194810)
        monitor.on_peer_snapshot([{"node_id": "firt node", "port": 19301},
                                  {"node_id": "second node", "port": 3193}])
        monitor.on_requestor_stats_snapshot(
            CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
            FinishedTasksStats(
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY))
        ccd = ClientConfigDescriptor()
        ccd.node_name = "new node name"
        nmm = NodeMetadataModel("CLIID", "SESSID", "win32", "1.3", ccd)
        monitor.on_config_update(nmm)
        monitor.on_logout()
        monitor.shut_down()

    def test_protocol_versions(self):
        """Test whether correct protocol versions were sent."""
        from golem.core.variables import PROTOCOL_CONST
        monitor = SystemMonitor(
            NodeMetadataModel("CLIID", "SESSID", "hackix", "3.1337",
                              ClientConfigDescriptor()), MONITOR_CONFIG)

        def check(f, msg_type):
            with mock.patch('golem.monitor.monitor.SenderThread.send') \
                    as mock_send:
                f()
                self.assertEqual(mock_send.call_count, 1)
                result = mock_send.call_args[0][0].dict_repr()
                for key in ('cliid', 'sessid', 'timestamp', 'metadata'):
                    del result[key]
                expected_d = {
                    'type': msg_type,
                    'protocol_versions': {
                        'monitor': MONITOR_CONFIG['PROTO_VERSION'],
                        'p2p': PROTOCOL_CONST.ID,
                        'task': PROTOCOL_CONST.ID,
                    },
                }
                self.assertEqual(expected_d, result)

        check(monitor.on_login, "Login")
        check(monitor.on_logout, "Logout")

    def test_ping_request(self):
        from pydispatch import dispatcher
        monitor = SystemMonitor(
            NodeMetadataModel("CLIID", "SESSID", "hackix", "3.1337",
                              ClientConfigDescriptor()), MONITOR_CONFIG)
        port = random.randint(20, 50000)
        with mock.patch('requests.post') as post_mock:
            post_mock.return_value = response_mock = mock.MagicMock()
            response_mock.json = mock.MagicMock(return_value={'success': True})
            dispatcher.send(signal='golem.p2p', event='no event at all',
                            port=port)
            self.assertEqual(post_mock.call_count, 0)
            dispatcher.send(signal='golem.p2p', event='listening', port=port)
            post_mock.assert_called_once_with(
                '%sping-me' % (MONITOR_CONFIG['HOST'],),
                data={'port': port},
                timeout=mock.ANY,
            )

            signals = []

            def l(sender, signal, event, **kwargs):  # noqa pylint: disable=unused-argument
                signals.append((signal, event, kwargs))

            dispatcher.connect(l, signal="golem.p2p")
            response_mock.json = mock.MagicMock(
                return_value={'success': False, 'description': 'failure'})
            dispatcher.send(signal='golem.p2p', event='listening', port=port)
            signals = [s for s in signals if s[1] != 'listening']
            self.assertEqual(signals, [('golem.p2p', 'unreachable',
                                        {'description': 'failure',
                                         'port': port})])
        # we keep active reference for dispatcher not to remove it
        del monitor


class TestSenderThread(TestCase):
    def test_run_exception(self):
        node_info = mock.Mock()
        node_info.dict_repr.return_value = dict()
        sender = SenderThread(
            node_info=node_info,
            monitor_host=None,
            monitor_request_timeout=0,
            monitor_sender_thread_timeout=0,
            proto_ver=None
        )
        sender.stop_request.isSet = mock.Mock(side_effect=[False, True])
        with mock.patch('requests.post',
                        side_effect=requests.exceptions.RequestException(
                            "request failed")), \
                self.assertLogs() as logs:
            sender.run()

        # make sure we're not spitting out stack traces
        assert len(logs.output) == 1
        output_lines = logs.output[0].split('\n')
        assert len(output_lines) == 1
