
def is_method_accessible(name, attr):
    return callable(attr) and not name.startswith('_')


def to_dict(service):
    methods = {}

    for method in dir(service):
        attr = getattr(service, method)
        if is_method_accessible(method, attr):
            methods[method] = attr

    return methods


def to_names_list(service):
    methods = []

    for method in dir(service):
        attr = getattr(service, method)
        if is_method_accessible(method, attr):
            methods.append(method)

    return methods


def full_name(service):
    return unicode(service.__module__ + "." + service.__class__.__name__)


def full_method_name(full_service_name, method_name):
    return unicode(full_service_name + "." + method_name)


class ServiceMethods(object):

    def __init__(self, service):
        self.methods = to_dict(service) if service else {}


class ServiceProxy(ServiceMethods):

    name_exceptions = ['parent' 'service', 'methods', 'name_exceptions', 'wrap']

    def __init__(self, service):
        ServiceMethods.__init__(self, service)
        for name, method in self.methods.iteritems():
            self.methods[name] = self.wrap(name, method)

    def __getattribute__(self, name, exceptions=None):
        exceptions = exceptions or ServiceProxy.name_exceptions

        if name.startswith('_') or name in exceptions:
            return object.__getattribute__(self, name)
        elif hasattr(self, 'methods'):
            return self.methods.get(name, None)
        return None

    def wrap(self, name, method):
        raise NotImplementedError()


class ServiceNameProxy(ServiceProxy):

    def __init__(self, method_names):
        ServiceMethods.__init__(self, None)
        for name in method_names:
            self.methods[name] = self.wrap(name, None)

    def wrap(self, name, method):
        raise NotImplementedError()
