from golem.core.keysauth import KeysAuth
from .httptransport import DefaultHttpSender
from .proto import DefaultProto


class DefaultJSONSender(object):
    def __init__(self, host, timeout, proto_ver,
                 sign_key: KeysAuth) -> None:
        self.transport = DefaultHttpSender(host, timeout, sign_key)
        self.proto = DefaultProto(proto_ver)

    def send(self, o, host: str = '', url_path: str = ''):
        msg = self.proto.prepare_json_message(o.dict_repr())
        return self.transport.post_json(msg, host, url_path)
