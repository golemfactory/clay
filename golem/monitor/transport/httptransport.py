import logging
import requests
import time

log = logging.getLogger('golem.monitor.transport')


class DefaultHttpSender(object):
    def __init__(self, url, request_timeout):
        self.url = url
        self.timeout = request_timeout
        self.json_headers = {'content-type': 'application/json'}
        self.last_exception_time = 0

    def _post(self, headers, payload):
        try:
            r = requests.post(self.url, data=payload, headers=headers,
                              timeout=self.timeout)
            return r.status_code == 200
        except requests.exceptions.RequestException as e:
            delta = time.time() - self.last_exception_time
            if delta > 60*10:  # seconds
                log.warning('Problem sending payload to: %r, because %s',
                            self.url, e)
                self.last_exception_time = time.time()
            return False

    def post_json(self, json_payload):
        return self._post(self.json_headers, json_payload)
