from .httptransport import DefaultHttpSender
from .proto import DefaultProto


class DefaultJSONSender(object):
    def __init__(self, host, timeout, proto_ver):
        self.transport = DefaultHttpSender(host, timeout)
        self.proto = DefaultProto(proto_ver)

    def send(self, o, host: str = '', url_path: str = ''):
        msg = self.proto.prepare_json_message(o.dict_repr())
        return self.transport.post_json(msg, host, url_path)
