import base64
import datetime
import logging
import queue
import threading
import time
from enum import Enum
from typing import Optional, Hashable
from urllib.parse import urljoin

import requests
import golem_messages
from golem_messages import message

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
    data = golem_messages.dump(msg, signing_key, variables.CONCENT_PUBKEY)
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

    elif response.status_code % 500 < 100:
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


class ConcentRequestStatus(Enum):

    Initial = object()
    Waiting = object()
    Queued = object()
    Success = object()
    TimedOut = object()
    Error = object()

    def completed(self) -> bool:
        return self.success() or self.error()

    def success(self) -> bool:
        return self == self.Success

    def error(self) -> bool:
        return self in (self.TimedOut, self.Error)


class ConcentRequest:

    __slots__ = ('key', 'msg', 'status', 'content',
                 'sent_at', 'deadline_at')

    def __init__(self,
                 key: Hashable,
                 msg: message.Message,
                 lifetime: datetime.timedelta) -> None:

        self.key = key
        self.msg = msg

        self.status = ConcentRequestStatus.Initial
        self.content = None

        self.sent_at = None
        self.deadline_at = datetime.datetime.now() + lifetime

    @staticmethod
    def build_key(*args) -> str:
        """
        Build a ConcentRequest key from the given arguments.

        :param args: Arguments to build a key with
        :return: str
        """
        return '/'.join(str(a) for a in args)

    def __repr__(self):
        return (
            "<ConcentRequest({}, {}, {}, sent_at={}, deadline_at={})>".format(
                self.key,
                self.msg,
                self.status.name,
                self.sent_at,
                self.deadline_at
            )
        )


class ConcentClientService(threading.Thread):

    MIN_GRACE_TIME = 5  # s
    MAX_GRACE_TIME = 5 * 60  # s
    GRACE_FACTOR = 2  # n times on each failure

    def __init__(self, signing_key, public_key, enabled=True):
        super().__init__(daemon=True)

        self.signing_key = signing_key
        self.public_key = public_key
        self._enabled = enabled  # FIXME: remove
        self._stop_event = threading.Event()

        self._queue = queue.Queue()
        self._grace_time = self.MIN_GRACE_TIME

        self._delayed = dict()
        self._history = dict()

    def run(self) -> None:
        while not self._stop_event.isSet():
            self._loop()
            time.sleep(1)

    def stop(self) -> None:
        self._stop_event.set()

    def submit(self,
               key: Hashable,
               msg: message.Message,
               delay: Optional[float] = None) -> None:
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
            delay = constants.MSG_DELAYS.get(msg_cls, 0)

        req = ConcentRequest(key, msg, lifetime=lifetime)
        req.status = ConcentRequestStatus.Waiting

        if delay:
            self._delayed[key] = reactor.callLater(delay, self._enqueue, req)
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

    def result(self,
               key: Hashable,
               default: Optional = None) -> Optional[ConcentRequest]:
        """
        Fetch and remove the ConcentRequest from queue.

        :param key: Request identifier
        :param default: Default value if key was not found
        :return: ConcentRequest|None
        """
        return self._history.pop(key, default)

    def _loop(self) -> None:
        """
        Main service loop. Requests from the queue are sent one by one (FIFO).
        In case of failure, service enters a grace period.
        """
        try:
            req = self._queue.get_nowait()
        except queue.Empty:
            return

        # FIXME: remove
        if not self._enabled:
            logger.debug('Concent disabled. Dropping %r', req)
            self._history.pop(req.key, None)
            return

        now = datetime.datetime.now()

        if req.deadline_at < now:
            logger.debug('Concent request lifetime has ended: %r', req)
            req.status = ConcentRequestStatus.TimedOut
            return

        try:
            req.sent_at = now
            res = send_to_concent(req.msg, self.signing_key, self.public_key)
        except Exception as exc:
            logger.exception('send_to_concent(%r) failed', req.msg)
            req.content = exc
            req.status = ConcentRequestStatus.Error
            self._grace_sleep()
        else:
            req.content = res
            req.status = ConcentRequestStatus.Success
            self._grace_time = self.MIN_GRACE_TIME

    def _grace_sleep(self):
        self._grace_time = min(self._grace_time * self.GRACE_FACTOR,
                               self.MAX_GRACE_TIME)

        logger.debug('Concent grace time: %r', self._grace_time)
        time.sleep(self._grace_time)

    def _enqueue(self, req):
        req.status = ConcentRequestStatus.Queued
        self._delayed.pop(req.key, None)
        self._history[req.key] = req
        self._queue.put(req)
