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


def int_to_string(item):
    # Deeply convert all integer elements of collections to string
    if isinstance(item, list):
        for k, v in enumerate(item):
            item[k] = int_to_string(v)
    elif isinstance(item, dict):
        for k, v in item.items():
            item[k] = int_to_string(v)
    elif isinstance(item, int):
        item = str(item)

    return item
