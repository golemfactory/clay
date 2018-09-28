import inspect
# SEE autobahn.twisted.wamp.Application.register


def expose(uri=None):  # pylint: disable=unused-argument
    def wrapper(f):
        nonlocal uri
        if uri is None:
            uri = '.'.join((
                'backend',
                f.__module__,
                f.__qualname__,
            ))
        if isinstance(f, (staticmethod, classmethod)):
            f.__func__.rpc_uri = uri
        else:
            f.rpc_uri = uri
        return f
    return wrapper


def object_method_map(instance):
    mapping = {}

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
