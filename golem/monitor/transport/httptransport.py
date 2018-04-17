import logging
import time
from typing import Optional
from urllib.parse import urljoin

import requests


log = logging.getLogger('golem.monitor.transport')


class DefaultHttpSender(object):
    def __init__(self, base_url, request_timeout):
        self.base_url = base_url
        self.timeout = request_timeout
        self.json_headers = {'content-type': 'application/json'}
        self.last_exception_time = 0

    def post(self, headers, payload,
             base_url: str, url_path: str) -> Optional[requests.Response]:
        try:
            if not base_url:
                base_url = self.base_url
            r = requests.post(urljoin(base_url, url_path),
                              data=payload,
                              headers=headers,
                              timeout=self.timeout)
            return r if r.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            delta = time.time() - self.last_exception_time
            if delta > 60*10:  # seconds
                log.warning('Problem sending payload to: %r, because %s',
                            urljoin(base_url, url_path), e)
                self.last_exception_time = time.time()
            return None

    def post_json(self, json_payload, base_url, url_path):
        return self.post(self.json_headers, json_payload, base_url, url_path)
