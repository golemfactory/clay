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
        self._is_available = None
        self._last_available_check = None

    def message(self, message):
        """
        Sends a message to the concent server

        :param message: The raw message to send
        :type message: String
        :return: Raw reply message, None or exception
        :rtype: String|None
        """
        if not self.__can_call_concent():
            raise ConcentGraceException("5 minute failure grace time")

        response = None
        try:
            response = requests.post(CONCENT_URL, data=message)
        except requests.exceptions.RequestException as e:
            if e.response:
                response = e.response
        else:
            if response.status_code == 200:
                self._is_available = True
                if response.text and response.text != "":
                    return response.text
                return None

        statuscode = -1
        body = "<EMPTY>"
        if response:
            if response.status_code:
                statuscode = response.status_code
            if response.text:
                body = response.text
        logger.warning('request failed with status %d and body: %r',
                       statuscode, body)

        self._last_available_check = time.time()
        self._is_available = False

        raise ConcentUnavailableException("Failed to call concent")

    def is_available(self):
        """
        Gives the status of the last Concent request

        :return: Was the last call successful, None when not called yet
        :rtype: Boolean|None
        """
        return self._is_available

    def __can_call_concent(self):
        if self._last_available_check is None:
            return True

        if self._last_available_check < time.time() - retry_time:
            return True

        return self._is_available
