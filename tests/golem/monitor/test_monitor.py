# pylint: disable=protected-access
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
from golem.monitor.monitor import SystemMonitor, SenderThread, Sender
from golem.monitorconfig import MONITOR_CONFIG
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats
from golem.tools.os_info import OSInfo

random = Random(__name__)


class MockSenderThread:
    def __init__(self):
        with mock.patch('golem.monitor.transport.sender.DefaultHttpSender'):
            self.sender = Sender('some_host', 'some_timeout',
                                 MONITOR_CONFIG['PROTO_VERSION'])

    def send(self, o):
        self.sender.send(o)

    def join(self):
        pass


class TestSystemMonitor(TestCase, testutils.PEP8MixIn):
    maxDiff = None
    PEP8_FILES = (
        "golem/monitor/monitor.py",
    )

    def setUp(self):
        client_mock = mock.MagicMock()
        client_mock.get_key_id = mock.MagicMock(return_value='cliid')
        client_mock.session_id = 'sessid'
        client_mock.config_desc = ClientConfigDescriptor()
        os_info = OSInfo(
            'linux',
            'Linux',
            '1',
            '1.2.3'
        )
        meta_data = NodeMetadataModel(
            client_mock, os_info, 'ver')
        config = MONITOR_CONFIG.copy()
        config['PING_ME_HOSTS'] = ['']
        self.monitor = SystemMonitor(meta_data, config)
        self.monitor._sender_thread = MockSenderThread()

    def tearDown(self):
        self.monitor.shut_down()

    def test_monitor_messages(self):
        """Just check if all signal handlers run without errors"""
        self.monitor.on_login()

        self.monitor.on_peer_snapshot([
            {"node_id": "first node", "port": 19301},
            {"node_id": "second node", "port": 3193}])
        self.monitor.on_requestor_stats_snapshot(
            CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
            FinishedTasksStats())
        ccd = ClientConfigDescriptor()
        ccd.node_name = "new node name"
        client_mock = mock.MagicMock()
        client_mock.get_key_id = mock.MagicMock(return_value='cliid')
        client_mock.session_id = 'sessid'
        client_mock.config_desc = ccd
        os_info = OSInfo(
            'win32',
            'Windows',
            '10',
            '10.2.23'
        )
        new_meta_data = NodeMetadataModel(
            client_mock, os_info, "1.3")
        self.monitor.on_config_update(new_meta_data)
        self.monitor.on_logout()

    def test_login_logout_messages(self):
        """Test whether correct login and logout messages
            and protocol data were sent."""

        def check(f, msg_type):
            with mock.patch('apps.core.nvgpu.is_supported', return_value=True):
                f()
            mock_send = self.monitor._sender_thread.sender.transport.post_json
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
                        'version': 'ver',
                        'settings': mock.ANY,
                        'os_info': mock.ANY
                    },
                    'cliid': 'cliid',
                    'sessid': 'sessid',
                    'timestamp': mock.ANY,
                    'nvgpu': {
                        'is_supported': True,
                    },
                }
            }
            self.assertEqual(expected_d, result)

        check(self.monitor.on_login, "Login")
        self.monitor._sender_thread.sender.transport.reset_mock()
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
            urljoin(self.monitor.config['PING_ME_HOSTS'][0], 'ping-me'),
            data={
                'ports': [port],
                'timestamp': time.time()
            },
            timeout=mock.ANY,
        )
        dispatcher.disconnect(listener, signal='golem.p2p')

    @mock.patch('requests.post')
    def test_ping_connection_error(self, post_mock: mock.MagicMock):
        post_mock.side_effect = requests.ConnectionError()

        def listener(event, *_, **__):
            if event != 'listening':
                self.fail()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=[])
        dispatcher.disconnect(listener, signal='golem.p2p')

    @mock.patch('requests.post')
    def test_ping_json_decode_error(self, post_mock: mock.MagicMock):
        post_mock().json.side_effect = json.JSONDecodeError('fail', '', 0)

        def listener(event, *_, **__):
            if event != 'listening':
                self.fail()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=[])
        dispatcher.disconnect(listener, signal='golem.p2p')

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
