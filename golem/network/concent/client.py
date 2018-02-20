import base64
import datetime
import logging
import queue
import threading
import time
import typing
from urllib.parse import urljoin

import requests
import golem_messages
from golem_messages import message
from golem_messages import datastructures as msg_datastructures

from golem import constants as gconst
from golem import utils
from golem.core import keysauth
from golem.core import variables
from golem.network.concent import constants
from golem.network.concent import exceptions

logger = logging.getLogger(__name__)


def verify_response(response: requests.Response) -> None:
    if response is None:
        raise exceptions.ConcentUnavailableError('response is None')

    logger.debug('Headers received from Concent: %s', response.headers)
    concent_version = response.headers['Concent-Golem-Messages-Version']
    if not utils.is_version_compatible(
            theirs=concent_version,
            spec=gconst.GOLEM_MESSAGES_SPEC,):
        raise exceptions.ConcentVersionMismatchError(
            'Incompatible version',
            ours=gconst.GOLEM_MESSAGES_VERSION,
            theirs=concent_version,
        )
    if response.status_code == 200:
        return

    if response.status_code % 500 < 100:
        raise exceptions.ConcentServiceError(
            "Concent service exception ({}): {}".format(
                response.status_code,
                response.text
            )
        )

    if response.status_code % 400 < 100:
        logger.warning('Concent request failed with status %d and '
                       'response: %r', response.status_code, response.text)

        raise exceptions.ConcentRequestError(
            "Concent request exception ({}): {}".format(
                response.status_code,
                response.text
            )
        )


def send_to_concent(msg: message.Message, signing_key, public_key) \
        -> typing.Optional[bytes]:
    """Sends a message to the concent server

    :return: Raw reply message, None or exception
    :rtype: Bytes|None
    """

    logger.debug('send_to_concent(): Encrypting msg %r', msg)
    data = golem_messages.dump(msg, signing_key, variables.CONCENT_PUBKEY)
    logger.debug('send_to_concent(): data: %r', data)
    concent_post_url = urljoin(variables.CONCENT_URL, '/api/v1/send/')
    headers = {
        'Content-Type': 'application/octet-stream',
        'Concent-Client-Public-Key': base64.standard_b64encode(public_key),
        'Concent-Other-Party-Public-Key': base64.standard_b64encode(b'dummy'),
        'X-Golem-Messages': golem_messages.__version__,
    }
    try:
        logger.debug(
            'send_to_concent(): POST %r hdr: %r',
            concent_post_url,
            headers,
        )
        response = requests.post(
            concent_post_url,
            data=data,
            headers=headers,
        )
    except requests.exceptions.RequestException as e:
        logger.warning('Concent RequestException %r', e)
        response = e.response

    verify_response(response)
    return response.content or None


def receive_from_concent(public_key) -> typing.Optional[bytes]:
    concent_receive_url = urljoin(variables.CONCENT_URL, '/api/v1/receive/')
    headers = {
        'Content-Type': 'application/octet-stream',
        'Concent-Client-Public-Key': base64.standard_b64encode(public_key),
        'X-Golem-Messages': golem_messages.__version__,
    }
    try:
        logger.debug(
            'receive_from_concent(): GET %r hdr: %r',
            concent_receive_url,
            headers,
        )
        response = requests.get(
            concent_receive_url,
            headers=headers,
        )
    except requests.exceptions.RequestException as e:
        raise exceptions.ConcentUnavailableError(
            'Failed to receive_from_concent()',
        ) from e

    verify_response(response)
    return response.content or None


class ConcentRequest(msg_datastructures.FrozenDict):
    ITEMS = {
        'key': '',
        'msg': None,
        'deadline_at': None,
    }

    @staticmethod
    def build_key(*args) -> str:
        """
        Build a ConcentRequest key from the given arguments.

        :param args: Arguments to build a key with
        :return: str
        """
        return '/'.join(str(a) for a in args)


class ConcentClientService(threading.Thread):

    MIN_GRACE_TIME = 5  # s
    MAX_GRACE_TIME = 5 * 60  # s
    GRACE_FACTOR = 2  # n times on each failure

    def __init__(self, keys_auth: keysauth.KeysAuth, enabled=True):
        super().__init__(daemon=True)

        self.keys_auth = keys_auth
        # self.private_key = private_key
        # self.public_key = public_key
        self._enabled = enabled  # FIXME: remove
        self._stop_event = threading.Event()

        self._queue = queue.Queue()
        self._grace_time = self.MIN_GRACE_TIME

        self._delayed = dict()
        self.received_messages = queue.Queue(maxsize=100)

    def run(self) -> None:
        while not self._stop_event.isSet():
            self._loop()
            self.receive()
            time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
        logger.info('Waiting for received messages queue to empty')
        self.received_messages.join()
        logger.info('%s stopped', self)

    def submit(self,
               key: typing.Hashable,
               msg: message.Message,
               delay: typing.Optional[datetime.timedelta] = None) -> None:
        """
        Submit a message to Concent.

        :param key: Request identifier
        :param delay: Time to wait before sending the message
        :return: None
        """
        from twisted.internet import reactor

        msg_cls = msg.__class__
        lifetime = constants.MSG_LIFETIMES.get(
            msg_cls,
            constants.DEFAULT_MSG_LIFETIME
        )
        if delay is None:
            delay = constants.MSG_DELAYS[msg_cls]

        req = ConcentRequest(
            key=key,
            msg=msg,
            deadline_at=datetime.datetime.now() + lifetime,
        )

        if delay:
            self._delayed[key] = reactor.callLater(
                delay.total_seconds(),
                self._enqueue,
                req,
            )
        else:
            self._enqueue(req)

    def cancel(self, key: typing.Hashable) -> bool:
        """
        Cancel a delayed Concent request.

        :param key: Request identifier
        :return: True if a request has been successfuly cancelled;
                 False otherwise
        """
        call = self._delayed.pop(key, None)
        if call:
            call.cancel()
            return True
        return False

    def _loop(self) -> None:
        """
        Main service loop. Requests from the queue are sent one by one (FIFO).
        In case of failure, service enters a grace period.
        """
        try:
            req = self._queue.get_nowait()
        except queue.Empty:
            return

        if not self._enabled:
            logger.debug('Concent disabled. Dropping %r', req)
            return

        now = datetime.datetime.now()

        if req['deadline_at'] < now:
            logger.debug('Concent request lifetime has ended: %r', req)
            return

        try:
            res = send_to_concent(
                req['msg'],
                self.keys_auth._private_key,  # pylint: disable=protected-access
                self.keys_auth.public_key,
            )
        except exceptions.ConcentError as e:
            logger.info('send_to_concent error: %s', e)
            self._grace_sleep()
        except Exception:  # pylint: disable=broad-except
            logger.exception('send_to_concent(%r) failed', req)
            self._grace_sleep()
        else:
            self._grace_time = self.MIN_GRACE_TIME
            self.react_to_concent_message(res)

    def receive(self) -> None:
        if not self._enabled:
            return

        try:
            res = receive_from_concent(self.keys_auth.public_key)
        except exceptions.ConcentError as e:
            logger.warning("Can't receive message from Concent: %s", e)
            self._grace_sleep()
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception('receive_from_concent() failed')
            self._grace_sleep()
            return
        self.react_to_concent_message(res)

    def react_to_concent_message(self, data: bytes):
        if data is None:
            return
        try:
            msg = golem_messages.load(
                data,
                self.keys_auth.ecc.raw_privkey,
                variables.CONCENT_PUBKEY,
            )
        except golem_messages.exceptions.MessageError as e:
            logger.warning("Can't deserialize concent message %s:%r", e, data)
            logger.debug('Problem parsing msg', exc_info=True)
            return
        self.received_messages.put(msg)

    def _grace_sleep(self):
        self._grace_time = min(self._grace_time * self.GRACE_FACTOR,
                               self.MAX_GRACE_TIME)

        logger.debug('Concent grace time: %r', self._grace_time)
        time.sleep(self._grace_time)

    def _enqueue(self, req):
        self._delayed.pop(req['key'], None)
        self._queue.put(req)
