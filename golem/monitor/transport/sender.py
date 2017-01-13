from golem.decorators import log_error
from httptransport import DefaultHttpSender
from proto import DefaultProto


class DefaultJSONSender(object):

    def __init__(self, host, timeout, proto_ver):
        self.transport = DefaultHttpSender(host, timeout)
        self.proto = DefaultProto(proto_ver)

    @classmethod
    def _obj2dict(cls, o):
        return o.dict_repr()

    @log_error(reraise=True)
    def send(self, o):
        dict_repr = DefaultJSONSender._obj2dict(o)

        msg = self.proto.prepare_json_message(dict_repr)

        return self.transport.post_json(msg)
