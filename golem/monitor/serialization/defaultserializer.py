import json


class DefaultJSONSerializer(object):

    @classmethod
    def dict2json(cls, d):
        return json.dumps(d, indent=4)


class DefaultSerializer(object):

    @classmethod
    def serialize(cls, typeid, o):
        d = cls.default_repr(typeid, o)

        return DefaultJSONSerializer.dict2json(d)

    @classmethod
    def deserialize(cls, s):
        return json.loads(s)

    @classmethod
    def default_repr(cls, typeid, o):
        d = {'type': typeid, 'obj': o.__dict__}

        return d
