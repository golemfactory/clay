import jsonpickle as json


def dict2json(d):
    return json.dumps(d, indent=4)


class DefaultSerializer(object):

    @classmethod
    def serialize(cls, typeid, o):
        d = cls.default_repr(typeid, o)

        return json.dumps(d)

    @classmethod
    def deserialize(cls, s):
        return json.loads(s)

    @classmethod
    def default_repr(cls, typeid, o):
        d = {'type': typeid, 'obj': o.__dict__}

        return d
