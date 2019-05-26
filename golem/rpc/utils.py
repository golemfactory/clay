import inspect
import typing
# SEE autobahn.twisted.wamp.Application.register


def expose(uri=None):  # pylint: disable=unused-argument
    def wrapper(f):
        nonlocal uri
        if uri is None:
            try:
                module_name = f.__module__
                qual_name = f.__qualname__
            except AttributeError:
                module_name = f.__func__.__module__
                qual_name = f.__func__.__qualname__
            uri = '.'.join((
                'backend',
                module_name,
                qual_name,
            ))
        if isinstance(f, (staticmethod, classmethod)):
            f.__func__.rpc_uri = uri
        else:
            f.rpc_uri = uri
        return f
    return wrapper


def object_method_map(instance):
    mapping: typing.Dict[str, typing.Callable] = {}

    # bounds methods are methods, class/static methods are functions (not bound)
    def predicate(member):
        return inspect.ismethod(member) \
            or inspect.isfunction(member)
    for _, method in inspect.getmembers(instance, predicate):
        try:
            uri = method.rpc_uri
        except AttributeError:
            continue
        mapping[uri] = method
    return mapping


def big_int_to_string(collection):
    # Deeply convert all big integer elements of collections to string
    def _big_int_to_string(v):
        if isinstance(v, dict) or isinstance(v, list):
            v = big_int_to_string(v)
        else:
            if isinstance(v, int) and v > (2**53) - 1:  # MAX SAFE INTEGER IN JS
                v = str(v)
        return v

    if isinstance(collection, list):
        for k, v in enumerate(collection):
            collection[k] = _big_int_to_string(v)
    elif isinstance(collection, dict):
        for k, v in collection.items():
            collection[k] = _big_int_to_string(v)

    return collection
