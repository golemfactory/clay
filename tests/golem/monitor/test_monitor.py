from base64 import b64decode
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
from golem.monitor.transport.sender import DefaultJSONSender as Sender

random = Random(__name__)


class TestSystemMonitor(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = (
        "golem/monitor/monitor.py",
    )

    def setUp(self):
        mock.patch('requests.post')
        client_mock = mock.MagicMock()
        client_mock.session_id = 'sessid'
        client_mock.config_desc = ClientConfigDescriptor()
        meta_data = NodeMetadataModel(
            client_mock, 'os', 'ver')
        config = MONITOR_CONFIG.copy()
        config['HOST'] = 'http://localhost/88881'
        config['PING_ME_HOSTS'] = ['http://localhost/88881']
        sign_mock = mock.MagicMock()
        sign_mock.public_key = b''
        sign_mock.sign.return_value = b''
        self.monitor = SystemMonitor(meta_data, config, sign_mock)
        self.monitor.start()

    def tearDown(self):
        self.monitor.stop()
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
        client_mock.session_id = 'sessid'
        client_mock.config_desc = ccd
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
                self.wait_for_first_call(mock_send)
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
                            'sessid': 'sessid',
                            'os': 'os',
                            'version': 'ver',
                            'settings': mock.ANY,
                        },
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

    @mock.patch('requests.post')
    def test_message_signature(self, post_mock):
        """ check whether messages are signed correctly """

        sign_key = mock.MagicMock()
        self.monitor.sender_thread.sender.transport.sign_key = sign_key
        sign_key.public_key = b'pubkey,'
        sign_key.sign = lambda m: bytes('len:'+str(len(m)), 'ascii')

        msg = mock.MagicMock()
        msg.dict_repr.return_value = {'a': 1, 'b': 'c', 'd': {}}
        self.monitor.sender_thread.process('send', msg=msg)

        self.wait_for_first_call(post_mock)

        signature = post_mock.call_args[1]['headers']['auth']
        self.assertEqual(b64decode(signature), b'pubkey,len:93')

    @freeze_time()
    @mock.patch('requests.post')
    def test_ping_request_success(self, post_mock):
        port = random.randint(40000, 50000)
        post_ret = post_mock()
        post_ret.status_code = 200
        post_ret.json.return_value = {
            'success': True,
            'time_diff': 0
        }

        self.monitor.ping_service.start = self.monitor.ping_service._run

        def listener(event, *_, **__):
            if event == 'unreachable':
                self.fail()
        dispatcher.connect(listener, signal='golem.p2p')

        post_mock.reset_mock()
        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=(port,))

        class JsonMatcher:  # pylint: disable=too-few-public-methods
            def __init__(self, **d):
                self.d = d

            def __eq__(self, msg):
                try:
                    if isinstance(msg, str):
                        msg = json.loads(msg)
                    for k, v in self.d.items():
                        if msg[k] != v:
                            return False
                    return True
                except (KeyError, json.JSONDecodeError):
                    return False

            def __ne__(self, v):
                return not self.__eq__(v)

        self.wait_for_call(
            post_mock,
            urljoin(self.monitor.config['HOST'], 'ping-me'),
            data=JsonMatcher(
                data=JsonMatcher(
                    ports=[port],
                    timestamp=mock.ANY)),
            headers=mock.ANY,
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
        port = random.randint(40000, 50000)
        post_ret = post_mock()
        post_ret.status_code = 200
        post_ret.json.return_value = {
            'success': False,
            'port_statuses': [{
                'port': port,
                'is_open': False,
                'description': 'timeout'
            }],
            'description': 'whatever',
            'time_diff': 0
        }

        self.monitor.ping_service.start = self.monitor.ping_service._run
        listener = mock.MagicMock()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=(port,))

        self.wait_for_call(
            listener,
            sender=mock.ANY,
            signal='golem.p2p',
            event='unreachable',
            port=port,
            description='timeout'
        )

    @mock.patch('requests.post')
    def test_ping_request_time_diff_too_big(self, post_mock):
        time_diff = variables.MAX_TIME_DIFF + 5
        post_ret = post_mock()
        post_ret.status_code = 200
        post_ret.json.return_value = {
            'success': True,
            'time_diff': time_diff
        }

        self.monitor.ping_service.start = self.monitor.ping_service._run
        listener = mock.MagicMock()
        dispatcher.connect(listener, signal='golem.p2p')

        dispatcher.send(
            signal='golem.p2p',
            event='listening',
            ports=())

        self.wait_for_call(
            listener,
            sender=mock.ANY,
            signal='golem.p2p',
            event='unsynchronized',
            time_diff=time_diff
        )

    def wait_for_first_call(self, listener):
        timeout = 1000
        while timeout and not listener.call_count:
            timeout -= 1
            time.sleep(0.001)
        if not timeout:
            self.fail()

    @staticmethod
    def wait_for_call(listener, *args, **kwargs):
        timeout = 1000
        expected = listener._call_matcher((args, kwargs))
        while timeout and expected not in\
                [listener._call_matcher(c) for c in listener.call_args_list]:
            timeout -= 1
            time.sleep(0.001)
        listener.assert_any_call(*args, **kwargs)


class TestSenderThread(TestCase):
    def test_run_exception(self):
        node_info = mock.Mock()
        node_info.dict_repr.return_value = dict()
        sign_mock = mock.MagicMock()
        sign_mock.public_key = b''
        sign_mock.sign.return_value = b''
        sender = SenderThread(
            node_info=node_info,
            config={'SENDER_THREAD_TIMEOUT': 0},
            sender=Sender(None, 0, 0, sign_mock)
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
