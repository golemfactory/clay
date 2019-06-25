# pylint: disable=protected-access, no-self-use
import datetime
import gc
import logging
import time
from unittest import mock, TestCase
import urllib

from pydispatch import dispatcher
import requests
from requests.exceptions import RequestException
from freezegun import freeze_time

import golem_messages
import golem_messages.cryptography
import golem_messages.exceptions
from golem_messages import message
from golem_messages import factories as msg_factories
from golem_messages.factories.helpers import (
    random_eth_address,
)

from golem import testutils
from golem.core import keysauth
from golem.core import variables
from golem.network import history
from golem.network.concent import client
from golem.network.concent import exceptions

logger = logging.getLogger(__name__)


class TestVerifyResponse(TestCase):
    def setUp(self):
        self.response = requests.Response()
        self.response.status_code = 200
        self.response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__

    def test_message_client_error(self):
        self.response.status_code = 400
        with self.assertRaises(exceptions.ConcentRequestError):
            client.verify_response(self.response)

    def test_message_server_error(self):
        self.response.status_code = 500
        with self.assertRaises(exceptions.ConcentServiceError):
            client.verify_response(self.response)

    def test_message_server_199(self):
        self.response.status_code = 199
        with self.assertRaises(exceptions.ConcentRequestError):
            client.verify_response(self.response)

    def test_message_server_200(self):
        self.response.status_code = 200
        client.verify_response(self.response)

    def test_message_server_299(self):
        self.response.status_code = 299
        client.verify_response(self.response)

    def test_message_server_300(self):
        self.response.status_code = 300
        with self.assertRaises(exceptions.ConcentRequestError):
            client.verify_response(self.response)

    def test_version_mismatch(self):
        self.response.headers['Concent-Golem-Messages-Version'] = 'dummy'
        with self.assertRaises(exceptions.ConcentVersionMismatchError):
            client.verify_response(self.response)

    def test_no_version(self):
        del self.response.headers['Concent-Golem-Messages-Version']
        with self.assertRaises(exceptions.ConcentVersionMismatchError):
            client.verify_response(self.response)


@mock.patch('requests.post')
class TestSendToConcent(TestCase):
    def setUp(self):
        self.msg = msg_factories.concents.ForceReportComputedTaskFactory()
        node_keys = golem_messages.cryptography.ECCx(None)
        self.private_key = node_keys.raw_privkey
        self.public_key = node_keys.raw_pubkey
        self.variant = variables.CONCENT_CHOICES['dev']

    def test_message(self, post_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response.status_code = 200
        post_mock.return_value = response

        client.send_to_concent(
            msg=self.msg,
            signing_key=self.private_key,
            concent_variant=self.variant,
        )
        api_send_url = urllib.parse.urljoin(
            self.variant['url'],
            '/api/v1/send/'
        )
        post_mock.assert_called_once_with(
            api_send_url,
            data=mock.ANY,
            headers=mock.ANY
        )

    def test_request_exception(self, post_mock):
        post_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableError):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                concent_variant=self.variant,
            )

        self.assertEqual(post_mock.call_count, 1)

    @mock.patch('golem.network.concent.client.verify_response')
    def test_verify_response(self, verify_mock, post_mock):
        response = requests.Response()
        post_mock.return_value = response
        client.send_to_concent(
            msg=self.msg,
            signing_key=self.private_key,
            concent_variant=self.variant,
        )
        verify_mock.assert_called_once_with(response)

    def test_sending_same_message_twice_does_not_raise(self, post_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response.status_code = 200
        post_mock.return_value = response

        self.msg.sign_message(self.private_key)
        try:
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                concent_variant=self.variant,
            )
        except golem_messages.exceptions.SignatureAlreadyExists:
            self.fail("Already existing signature should be cleared"
                      " in `send_to_concent` function!")

    @mock.patch('golem.network.concent.client.verify_response')
    def test_delayed_timestamp(self, *_):
        future = datetime.datetime.utcnow() + datetime.timedelta(days=5)
        # messages use integer timestamps
        future = future.replace(microsecond=0)
        # freezegun requires naive datetime, .timestamp() works only with aware
        future_aware = future.replace(tzinfo=datetime.timezone.utc)
        with freeze_time(future):
            client.send_to_concent(
                msg=self.msg,
                signing_key=self.private_key,
                concent_variant=self.variant,
            )
        self.assertEqual(
            self.msg.timestamp,
            future_aware.timestamp(),
        )


@mock.patch('requests.post')
class TestReceiveFromConcent(TestCase):
    def setUp(self):
        self.msg = msg_factories.concents.ForceReportComputedTaskFactory()
        node_keys = golem_messages.cryptography.ECCx(None)
        self.private_key = node_keys.raw_privkey
        self.public_key = node_keys.raw_pubkey
        self.variant = variables.CONCENT_CHOICES['dev']

    def test_empty_content(self, get_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response._content = b''
        response.status_code = 200
        get_mock.return_value = response
        result = client.receive_from_concent(
            signing_key=self.private_key,
            public_key=self.public_key,
            concent_variant=self.variant,
        )
        self.assertIsNone(result)

    def test_content(self, get_mock):
        response = requests.Response()
        response.headers['Concent-Golem-Messages-Version'] = \
            golem_messages.__version__
        response._content = content = object()
        response.status_code = 200
        get_mock.return_value = response
        result = client.receive_from_concent(
            signing_key=self.private_key,
            public_key=self.public_key,
            concent_variant=self.variant,
        )
        self.assertIs(result, content)

    def test_request_exception(self, get_mock):
        get_mock.side_effect = RequestException
        with self.assertRaises(exceptions.ConcentUnavailableError):
            client.receive_from_concent(
                signing_key=self.private_key,
                public_key=self.public_key,
                concent_variant=self.variant,
            )

        self.assertEqual(get_mock.call_count, 1)

    @mock.patch('golem.network.concent.client.verify_response')
    def test_verify_response(self, verify_mock, get_mock):
        response = requests.Response()
        get_mock.return_value = response
        client.receive_from_concent(
            signing_key=self.private_key,
            public_key=self.public_key,
            concent_variant=self.variant,
        )
        verify_mock.assert_called_once_with(response)


@mock.patch('golem.terms.ConcentTermsOfUse.are_accepted', return_value=True)
@mock.patch('twisted.internet.reactor', create=True)
@mock.patch('golem.network.concent.client.receive_from_concent')
@mock.patch('golem.network.concent.client.send_to_concent')
class TestConcentClientService(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        keys_auth = keysauth.KeysAuth(
            datadir=self.path,
            private_key_name='priv_key',
            password='password',
        )
        self.concent_service = client.ConcentClientService(
            keys_auth=keys_auth,
            variant=variables.CONCENT_CHOICES['dev'],
        )
        self.msg = message.concents.ForceReportComputedTask()

    def tearDown(self):
        self.assertFalse(self.concent_service.isAlive())
        self.concent_service.stop()

    @mock.patch('golem.network.concent.client.ConcentClientService.receive')
    @mock.patch('golem.network.concent.client.ConcentClientService._loop')
    def test_start_stop(self, loop_mock, receive_mock, *_):
        self.concent_service.start()
        time.sleep(.5)
        self.concent_service.stop()
        self.concent_service.join(timeout=3)

        loop_mock.assert_called_once_with()
        receive_mock.assert_called_once_with()

    def test_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(),
        )

        assert 'key' not in self.concent_service._delayed

        assert not self.concent_service.cancel('key')

        assert 'key' not in self.concent_service._delayed

    def test_delayed_submit(self, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(seconds=60)
        )

        assert 'key' in self.concent_service._delayed

        assert self.concent_service.cancel('key')

        assert 'key' not in self.concent_service._delayed

    def test_loop_exception(self, send_mock, *_):
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(),
        )

        send_mock.side_effect = exceptions.ConcentRequestError
        mock_path = ("golem.network.concent.client.ConcentClientService"
                     "._grace_sleep")
        with mock.patch(mock_path) as sleep_mock:
            self.concent_service._loop()
            sleep_mock.assert_called_once_with()

        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.keys_auth._private_key,
            concent_variant=self.concent_service.variant,
        )

        assert not self.concent_service._delayed

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_loop(self, react_mock, send_mock, *_):
        data = object()
        send_mock.return_value = data
        self.concent_service.submit(
            'key',
            self.msg,
            delay=datetime.timedelta(),
        )

        self.concent_service._loop()
        send_mock.assert_called_once_with(
            self.msg,
            self.concent_service.keys_auth._private_key,
            concent_variant=self.concent_service.variant,
        )
        react_mock.assert_called_once_with(data, response_to=self.msg)

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive(self, react_mock, _send_mock, receive_mock, *_):
        receive_mock.return_value = content = 'rcv_content'
        self.concent_service.receive()
        receive_mock.assert_called_once_with(
            signing_key=self.concent_service.keys_auth._private_key,
            public_key=self.concent_service.keys_auth.public_key,
            concent_variant=self.concent_service.variant,
        )
        react_mock.assert_has_calls(
            (
                mock.call(content),
            ),
        )

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '._grace_sleep'
    )
    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive_concent_error(self,
                                   react_mock,
                                   sleep_mock,
                                   _send_mock,
                                   receive_mock,
                                   *_):
        receive_mock.side_effect = exceptions.ConcentError
        self.concent_service.receive()
        receive_mock.assert_called_once_with(
            signing_key=mock.ANY,
            public_key=mock.ANY,
            concent_variant=self.concent_service.variant,
        )
        sleep_mock.assert_called_once_with()
        react_mock.assert_not_called()

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '._grace_sleep'
    )
    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.react_to_concent_message'
    )
    def test_receive_exception(self,
                               react_mock,
                               sleep_mock,
                               _send_mock,
                               receive_mock,
                               *_):
        receive_mock.side_effect = Exception
        self.concent_service.receive()
        receive_mock.assert_called_once_with(
            signing_key=mock.ANY,
            public_key=mock.ANY,
            concent_variant=mock.ANY,
        )
        sleep_mock.assert_called_once_with()
        react_mock.assert_not_called()

    def test_react_to_concent_message_none(self, *_):
        result = self.concent_service.react_to_concent_message(None)
        self.assertIsNone(result)

    @mock.patch(
        'golem_messages.load',
        side_effect=golem_messages.exceptions.MessageError,
    )
    def test_react_to_concent_message_error(self, load_mock, *_):
        self.concent_service.received_messages.put = mock.Mock()
        data = object()
        result = self.concent_service.react_to_concent_message(data)
        self.assertIsNone(result)
        self.assertEqual(
            self.concent_service.received_messages.put.call_count,
            0,
        )
        load_mock.assert_called_once_with(
            data,
            self.concent_service.keys_auth._private_key,
            self.concent_service.variant['pubkey'],
        )

    @mock.patch('golem_messages.load')
    def test_react_to_concent_message(self, load_mock, *_):
        self.concent_service.received_messages.put = mock.Mock()
        data = object()
        load_mock.return_value = msg = mock.Mock()
        result = self.concent_service.react_to_concent_message(data)
        self.assertIsNone(result)
        self.concent_service.received_messages.put.assert_called_once_with(msg)
        load_mock.assert_called_once_with(
            data,
            self.concent_service.keys_auth._private_key,
            self.concent_service.variant['pubkey'],
        )


class ConcentCallLaterTestCase(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.concent_service = client.ConcentClientService(
            keys_auth=keysauth.KeysAuth(
                datadir=self.path,
                private_key_name='priv_key',
                password='password',
            ),
            variant=variables.CONCENT_CHOICES['dev'],
        )
        self.msg = message.concents.ForceReportComputedTask()

    def tearDown(self):
        self.concent_service.stop()

    def test_submit(self):
        # Shouldn't fail
        self.concent_service.submit(
            'key',
            self.msg,
            datetime.timedelta(seconds=1)
        )


class OverdueIncomeTestCase(testutils.DatabaseFixture):
    maxDiff = None

    def setUp(self):
        super().setUp()
        gc.collect()
        # unfortunately dispatcher.disconnect won't do the job
        dispatcher.connections = {}
        dispatcher.senders = {}
        dispatcher.sendersBack = {}
        self.concent_service = client.ConcentClientService(
            keys_auth=keysauth.KeysAuth(
                datadir=self.path,
                private_key_name='priv_key',
                password='password',
            ),
            variant=variables.CONCENT_CHOICES['dev'],
        )
        from golem.ethereum.incomeskeeper import IncomesKeeper
        self.incomes_keeper = IncomesKeeper()
        self.history = history.MessageHistoryService()

    def tearDown(self):
        self.history.stop()
        self.concent_service.stop()
        history.MessageHistoryService.instance = None

    @mock.patch(
        'golem.network.concent.client.ConcentClientService'
        '.submit_task_message')
    def test_submit(self, submit_mock):
        sra1 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            payment_ts=int(time.time()) - 3600*26,
            report_computed_task__task_to_compute__concent_enabled=True,
        )
        sra2 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            payment_ts=int(time.time()) - 3600*25,
            report_computed_task__task_to_compute__concent_enabled=True,
        )
        sra3 = msg_factories.tasks.SubtaskResultsAcceptedFactory(
            payment_ts=int(time.time()) - 3600*25,
        )

        local_role = history.Actor.Provider
        remote_role = history.Actor.Requestor
        for msg in (sra1, sra2, sra3):
            msg._fake_sign()
            history.add(
                msg=msg,
                node_id='requestor_id',
                local_role=local_role,
                remote_role=remote_role,
                sync=True,
            )
            self.incomes_keeper.expect(
                sender_node='requestor_id',
                task_id=msg.task_id,
                subtask_id=msg.subtask_id,
                payer_address='0x1234',
                my_address=random_eth_address(),
                value=msg.task_to_compute.price,  # pylint: disable=no-member
                accepted_ts=msg.payment_ts,
            )
        self.incomes_keeper.update_overdue_incomes()
        submit_mock.assert_called_once_with(
            subtask_id=mock.ANY,
            msg=mock.ANY,
        )
        fp = submit_mock.call_args[1]['msg']
        self.assertIsInstance(fp, message.concents.ForcePayment)
        self.assertEqual(
            fp.subtask_results_accepted_list,
            [
                sra1,
                sra2,
            ],
        )
