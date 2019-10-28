# pylint: disable=protected-access
import asyncio
import json
from unittest import mock, TestCase
from urllib.parse import urljoin

from random import Random
import requests
from pydispatch import dispatcher

from golem import testutils
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core import variables
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MONITOR_CONFIG
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats, \
    EMPTY_FINISHED_SUMMARY
from golem.tools.os_info import OSInfo

random = Random(__name__)


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
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        asyncio.set_event_loop(None)

    def test_monitor_messages(self):
        """Just check if all signal handlers run without errors"""
        self.loop.run_until_complete(self.monitor.on_login())

        self.loop.run_until_complete(self.monitor.on_peer_snapshot([
            {"node_id": "first node", "port": 19301},
            {"node_id": "second node", "port": 3193}]))
        self.loop.run_until_complete(self.monitor.on_requestor_stats_snapshot(
            CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
            FinishedTasksStats(
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY,
                EMPTY_FINISHED_SUMMARY)))
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
        self.loop.run_until_complete(
            self.monitor.on_config_update(new_meta_data),
        )
        self.loop.run_until_complete(self.monitor.on_logout())

    def test_login_logout_messages(self):
        """Test whether correct login and logout messages
            and protocol data were sent."""

        @mock.patch('requests.post')
        @mock.patch('json.dumps')
        def check(f, msg_type, mock_dumps, *_):
            with mock.patch('apps.core.nvgpu.is_supported', return_value=True):
                self.loop.run_until_complete(f())
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
            mock_dumps.assert_called_once_with(expected_d, indent=mock.ANY)

        # pylint: disable=no-value-for-parameter
        check(self.monitor.on_login, "Login")
        check(self.monitor.on_logout, "Logout")
        # pylint: enable=no-value-for-parameter

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
        self.loop.run_until_complete(self.monitor.ping_request([port]))
        post_mock.assert_called_once_with(
            urljoin(self.monitor.config['PING_ME_HOSTS'][0], 'ping-me'),
            data={
                'ports': [port],
                'timestamp': mock.ANY,
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

        self.loop.run_until_complete(self.monitor.ping_request([port]))

        listener.assert_called_once_with(
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
        self.loop.run_until_complete(self.monitor.ping_request([]))
        post_mock.assert_called_once()

        listener.assert_called_once_with(
            sender=mock.ANY,
            signal='golem.p2p',
            event='unsynchronized',
            time_diff=time_diff
        )

    @mock.patch(
        'requests.post',
        side_effect=requests.exceptions.RequestException("request failed"),
    )
    def test_requests_exception(self, *_):
        with self.assertLogs(logger='golem.monitor', level='WARNING') as logs:
            self.loop.run_until_complete(self.monitor.on_login())

        # make sure we're not spitting out stack traces
        assert len(logs.output) == 1
        output_lines = logs.output[0].split('\n')
        assert len(output_lines) == 1
