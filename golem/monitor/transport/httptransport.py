import requests


class DefaultHttpSender(object):

    def __init__(self, url, request_timeout):
        self.url = url
        self.timeout = request_timeout
        self.json_headers = {'content-type': 'application/json'}

    def _post(self, headers, payload):
        try:
            r = requests.post(self.url, data=payload, headers=headers, timeout=self.timeout)
            return r.status_code == 200
        except requests.exceptions.RequestException as ex:
            # FIXME: log request failure here
            return False

    def post_json(self, json_payload):
        return self._post(self.json_headers, json_payload)
