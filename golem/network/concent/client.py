import logging
import time

import requests

from golem.core.variables import CONCENT_URL

logger = logging.getLogger(__name__)

retry_time = 5 * 60


class ConcentException(Exception):
    """
    General exception for all Concent related errors
    """
    pass


class ConcentUnavailableException(ConcentException):
    """
    Called Concent but it is unavailble
    """
    pass


class ConcentGraceException(ConcentException):
    """
    Did not call concent due to grace period of previously failed call
    """
    pass


class ConcentClient:

    def __init__(self):
        self.is_available = None

        self._last_available_check = None

    def send(self, message):
        """
        Sends a message to the concent server

        :param message: The raw message to send
        :type message: String
        :return: Raw reply message, None or exception
        :rtype: String|None
        """
        if not self.can_call_concent():
            raise ConcentGraceException("5 minute failure grace time")

        response = None
        try:
            response = requests.post(CONCENT_URL, data=message)
        except requests.exceptions.RequestException as e:
            logger.warning('Concent RequestException %r', e)
            if e.response:
                response = e.response

        if response is None or response.status_code != 200:
            if response:
                logger.warning('request failed with status %d and body: %r',
                               response.status_code, response.text)

            self._last_available_check = time.time()
            self.is_available = False

            raise ConcentUnavailableException("Failed to call concent")

        self.is_available = True
        if not response.text or response.text == "":
            return None
        return response.text

    def can_call_concent(self):
        if self._last_available_check is None:
            return True

        if self._last_available_check < time.time() - retry_time:
            return True

        return self.is_available
