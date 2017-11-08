import logging
import time

import requests

from golem.core.variables import CONCENT_URL

logger = logging.getLogger(__name__)

retry_time = 5 * 60


class ConcentClient:

    def __init__(self):
        self._is_available = False
        self._last_available_check = None

    def message(self, message):

        print('message')
        if not self.__can_call_concent():
            raise Exception("5 minute failure grace time")

        try:
            response = requests.post(CONCENT_URL, data=message)
        except requests.RequestException as e:
            logger.warning('request failed with status %d and body: %r',
                           e.response.statuscode,
                           e.response.body)
        else:
            if response.statuscode == 200:
                self._is_available = True
                if response.body and response.body != "":
                    return response.body
                return None

        # TODO: only unavailable on certain errors
        print('call_time')
        cur_time = time.time()
        print(cur_time)

        self._last_available_check = cur_time
        self._is_available = False

        raise Exception("Failed to call concent")

    def is_available(self):
        return self._is_available

    def __can_call_concent(self):
        if self._last_available_check is None:
            print('is none')
            return True

        print('call_time')
        cur_time = time.time()
        print(cur_time)

        if self._last_available_check < cur_time - retry_time:
            return True

        return self._is_available
