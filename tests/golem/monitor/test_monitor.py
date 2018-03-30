import json
import time
from unittest import mock, TestCase
from urllib.parse import urljoin

from random import Random
import requests
from freezegun import freeze_time
from pydispatch import dispatcher

from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core import variables
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor, SenderThread
from golem.monitorconfig import MONITOR_CONFIG
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats, \
    EMPTY_FINISHED_SUMMARY

random = Random(__name__)


class TestSystemMonitor(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = (
        "golem/monitor/monitor.py",
    )

    def setUp(self):
        client_mock = mock.MagicMock()
        client_mock.get_key_id = mock.MagicMock(return_value='cliid')
        client_mock.session_id = 'sessid'
        client_mock.config_desc = ClientConfigDescriptor()
        client_mock.mainnet = False
        meta_data = NodeMetadataModel(
            client_mock, 'os', 'ver')
        config = MONITOR_CONFIG.copy()
        config['HOST'] = 'http://localhost/88881'
        config['SENDER_THREAD_TIMEOUT'] = 0.05
        self.monitor = SystemMonitor(meta_data, config)
        self.monitor.start()

    def tearDown(self):
        self.monitor.shut_down()
        del self.monitor

    def test_monitor_messages(self):
        """Just check if all signal handlers run without errors"""
        self.monitor.on_login()

        self.monitor.on_payment(addr="some address", value=30139019301)
        self.monitor.on_income("different address", 319031904194810)
        self.monitor.on_peer_snapshot([
            {"node_id": "first node", "port": 19301},
            {"node_id": "second node", "port": 3193}])
        self.monitor.on_requestor_stats_snapshot(
            CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
            FinishedTasksStats(
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY))
        ccd = ClientConfigDescriptor()
        ccd.node_name = "new node name"
        client_mock = mock.MagicMock()
        client_mock.cliid = 'CLIID'
        client_mock.sessid = 'SESSID'
        client_mock.config_desc = ccd
        client_mock.mainnet = False
        new_meta_data = NodeMetadataModel(
            client_mock, "win32", "1.3")
        self.monitor.on_config_update(new_meta_data)
        self.monitor.on_logout()

    def test_login_logout_messages(self):
        """Test whether correct login and logout messages
            and protocol data were sent."""

        def check(f, msg_type):
            with mock.patch(
                'golem.monitor.transport.httptransport.'
                + 'DefaultHttpSender.post_json') \
                    as mock_send:
                f()
                time.sleep(0.005)
                self.assertEqual(mock_send.call_count, 1)
                result = json.loads(mock_send.call_args[0][0])
                expected_d = {
                    'proto_ver': MONITOR_CONFIG['PROTO_VERSION'],
                    'data': {
                        'type': msg_type,
                        'protocol_versions': {
                            'monitor': self.monitor.config['PROTO_VERSION'],
                            'p2p': variables.PROTOCOL_CONST.ID,
                            'task': variables.PROTOCOL_CONST.ID,
                        },
                        'metadata': {
                            'type': 'NodeMetadata',
                            'net': 'testnet',
                            'timestamp': mock.ANY,
                            'cliid': 'cliid',
                            'sessid': 'sessid',
                            'os': 'os',
                            'version': 'ver',
                            'settings': mock.ANY,
                        },
                        'cliid': 'cliid',
                        'sessid': 'sessid',
                        'timestamp': mock.ANY,
                    }
                }
                self.assertEqual(expected_d, result)

        check(self.monitor.on_login, "Login")
        check(self.monitor.on_logout, "Logout")

    @mock.patch('requests.post')
    def test_ping_request_wrong_signal(self, post_mock):
        dispatcher.send(
            signal='golem.p2p',
            event='no event at all',
            ports=[])
        self.assertEqual(post_mock.call_count, 0)

    @freeze_time()
    @mock.patch('requests.post')
    def test_ping_request_success(self, post_mock):
        port = random.randint(1, 65535)
        post_mock.return_value.json.return_value = {
            'success': True,
            'time_diff': 0
        }

        def listener(event, *_, **__):
            if event == 'unreachable':
                self.fail()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=[port])
        post_mock.assert_called_once_with(
            urljoin(self.monitor.config['HOST'], 'ping-me'),
            data={
                'ports': [port],
                'timestamp': time.time()
            },
            timeout=mock.ANY,
        )

    @mock.patch('requests.post')
    def test_ping_request_port_unreachable(self, post_mock):
        port = random.randint(1, 65535)
        post_mock.return_value.json.return_value = {
            'success': False,
            'port_statuses': [{
                'port': port,
                'is_open': False,
                'description': 'timeout'
            }],
            'description': 'whatever',
            'time_diff': 0
        }

        listener = mock.MagicMock()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=[port])

        listener.assert_any_call(
            sender=mock.ANY,
            signal='golem.p2p',
            event='unreachable',
            port=port,
            description='timeout'
        )

    @mock.patch('requests.post')
    def test_ping_request_time_diff_too_big(self, post_mock):
        time_diff = variables.MAX_TIME_DIFF + 5
        post_mock.return_value.json.return_value = {
            'success': True,
            'time_diff': time_diff
        }

        listener = mock.MagicMock()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=[])

        listener.assert_any_call(
            sender=mock.ANY,
            signal='golem.p2p',
            event='unsynchronized',
            time_diff=time_diff
        )


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
