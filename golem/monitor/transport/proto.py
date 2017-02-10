from golem.monitor.serialization.defaultserializer import dict2json


class DefaultProto(object):
    def __init__(self, proto_version):
        self.proto_version = proto_version

    def prepare_json_message(self, d):
        json_dict = {'proto_ver': self.proto_version, 'data': d}
        return dict2json(json_dict)
