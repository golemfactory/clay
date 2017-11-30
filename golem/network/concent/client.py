import logging
import queue
import threading
import time
from enum import Enum
from typing import Optional, Hashable, Type

import requests
from golem_messages import message

from golem.core.variables import CONCENT_URL
from golem.network.concent.constants import MSG_DELAYS, MSG_LIFETIMES, \
    DEFAULT_MSG_LIFETIME
from golem.network.concent.exceptions import ConcentUnavailableException, \
    ConcentServiceException, ConcentRequestException

logger = logging.getLogger(__name__)


class ConcentClient:

    @classmethod
    def send(cls,
             data: bytes,
             url: str = CONCENT_URL) -> Optional[str]:
        """
        Sends a message to the concent server

        :param data: Serialized message to send
        :param url: Concent API endpoint URL
        :return: Raw reply message, None or exception
        :rtype: Bytes|None
        """

        try:
            response = requests.post(url, data=data)
        except requests.exceptions.RequestException as e:
            logger.warning('Concent RequestException %r', e)
            response = e.response

        if response is None:
            raise ConcentUnavailableException()

        elif response.status_code % 500 < 100:
            logger.warning('Concent failed with status %d and body: %r',
                           response.status_code, response.text)

            raise ConcentServiceException("Concent service exception ({}): {}"
                                          .format(response.status_code,
                                                  response.text))

        elif response.status_code % 400 < 100:
            logger.warning('Concent request failed with status %d and '
                           'response: %r', response.status_code, response.text)

            raise ConcentRequestException("Concent request exception ({}): {}"
                                          .format(response.status_code,
                                                  response.text))

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

    __slots__ = ('key', 'msg_data', 'msg_cls', 'status', 'content',
                 'sent_ts', 'deadline_ts')

    def __init__(self,
                 key: Hashable,
                 msg_data: bytes,
                 msg_cls: Type[message.Message],
                 lifetime: float) -> None:

        self.key = key
        self.msg_data = msg_data
        self.msg_cls = msg_cls

        self.status = ConcentRequestStatus.Initial
        self.content = None

        self.sent_ts = None
        self.deadline_ts = time.time() + lifetime

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
            "<ConcentRequest({}, {}, {}, sent_ts={}, deadline_ts={})>".format(
                self.key,
                self.msg_cls,
                self.status.name,
                self.sent_ts,
                self.deadline_ts
            )
        )


class ConcentClientService(threading.Thread):

    MIN_GRACE_TIME = 5.  # s
    MAX_GRACE_TIME = 5. * 60  # s
    GRACE_FACTOR = 2  # n times on each failure

    QUEUE_TIMEOUT = 5  # s

    def __init__(self, enabled=True):
        super().__init__(daemon=True)

        self._enabled = enabled  # FIXME: remove
        self._stop_event = threading.Event()

        self._queue = queue.Queue()
        self._client = ConcentClient()
        self._grace_time = self.MIN_GRACE_TIME

        self._delayed = dict()
        self._history = dict()

    def run(self) -> None:
        while not self._stop_event.isSet():
            self._loop()

    def stop(self) -> None:
        self._stop_event.set()

    def submit(self,
               key: Hashable,
               msg_data: bytes,
               msg_cls: Type[message.Message],
               delay: Optional[float] = None) -> None:
        """
        Submit a message to Concent.

        :param key: Request identifier
        :param msg_data: Serialized message to send
        :param msg_cls: Class of the sent message
        :param delay: Time to wait before sending the message
        :return: None
        """
        from twisted.internet import reactor

        lifetime = MSG_LIFETIMES.get(msg_cls, DEFAULT_MSG_LIFETIME)
        if delay is None:
            delay = MSG_DELAYS.get(msg_cls, 0)

        req = ConcentRequest(key, msg_data, msg_cls, lifetime=lifetime)
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
            req = self._queue.get(True, self.QUEUE_TIMEOUT)
        except queue.Empty:
            return

        # FIXME: remove
        if not self._enabled:
            self._history.pop(req.key, None)
            return

        now = time.time()

        if req.deadline_ts < now:
            logger.debug('Concent request lifetime has ended: %r', req)
            req.status = ConcentRequestStatus.TimedOut
            return

        try:
            req.sent_ts = now
            res = self._client.send(req.msg_data)
        except Exception as exc:
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
