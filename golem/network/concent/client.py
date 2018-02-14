import base64
import datetime
import logging
import queue
import threading
import time
from typing import Optional, Hashable
from urllib.parse import urljoin

import requests
import golem_messages
from golem_messages import message
from golem_messages import datastructures as msg_datastructures

from golem.core import keysauth
from golem.core import variables
from golem.network.concent import constants
from golem.network.concent import exceptions

logger = logging.getLogger("golem.network.concent.client")


def send_to_concent(msg: message.Message, signing_key, public_key) \
        -> Optional[str]:
    """Sends a message to the concent server

    :return: Raw reply message, None or exception
    :rtype: Bytes|None
    """

    logger.debug('send_to_concent(): Encrypting msg %r', msg)
    if msg is not None:
        data = golem_messages.dump(msg, signing_key, variables.CONCENT_PUBKEY)
    else:
        data = b''
    logger.debug('send_to_concent(): data: %r', data)
    concent_post_url = urljoin(variables.CONCENT_URL, '/api/v1/send/')
    headers = {
        'Content-Type': 'application/octet-stream',
        'Concent-Client-Public-Key': base64.standard_b64encode(public_key),
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

    if response is None:
        raise exceptions.ConcentUnavailableException()

    logger.debug('Headers received from Concent: %s', response.headers)
    if response.status_code % 500 < 100:
        logger.warning('Concent failed with status %d and body: %r',
                       response.status_code, response.text)

        raise exceptions.ConcentServiceException(
            "Concent service exception ({}): {}".format(
                response.status_code,
                response.text
            )
        )

    elif response.status_code % 400 < 100:
        logger.warning('Concent request failed with status %d and '
                       'response: %r', response.status_code, response.text)

        raise exceptions.ConcentRequestException(
            "Concent request exception ({}): {}".format(
                response.status_code,
                response.text
            )
        )

    return response.content or None


class ConcentRequest(msg_datastructures.FrozenDict):

    __slots__ = ('key', 'msg', 'sent_at', 'deadline_at')
    ITEMS = {
        'key': '',
        'msg': None,
        'sent_at': None,
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

    def __init__(self, keys_auth: keysauth.EllipticalKeysAuth, enabled=True):
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
            time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()
        logger.info('Waiting for received messages queue to empty')
        self.received_messages.join()
        logger.info('%s stopped', self)

    def submit(self,
               key: Hashable,
               msg: message.Message,
               delay: Optional[datetime.timedelta] = None) -> None:
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

    def cancel(self, key: Hashable) -> bool:
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
            req = self._queue.get(timeout=constants.PING_TIMEOUT)
        except queue.Empty:
            # Send empty "ping" message
            res = send_to_concent(
                None,
                self.keys_auth._private_key,  # pylint: disable=protected-access
                self.keys_auth.public_key,
            )
            self.react_to_concent_message(res)
            return

        # FIXME: remove
        if not self._enabled:
            logger.debug('Concent disabled. Dropping %r', req)
            return

        now = datetime.datetime.now()

        if req['deadline_at'] < now:
            logger.debug('Concent request lifetime has ended: %r', req)
            return

        try:
            req['sent_at'] = now
            res = send_to_concent(
                req['msg'],
                self.keys_auth.ecc.raw_privkey,
                self.keys_auth.ecc.raw_pubkey,
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception('send_to_concent(%r) failed', req)
            self._grace_sleep()
        else:
            self._grace_time = self.MIN_GRACE_TIME
            self.react_to_concent_message(res)

    def react_to_concent_message(self, data):
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
