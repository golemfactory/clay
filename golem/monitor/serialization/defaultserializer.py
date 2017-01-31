import functools
import json


dict2json = functools.partial(json.dumps, indent=4)


def serialize(typeid, o):
    d = {'type': typeid, 'obj': o.__dict__}
    return json.dumps(d)
