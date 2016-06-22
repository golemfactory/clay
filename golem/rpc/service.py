class ServiceMethods(object):

    def __init__(self, service):
        self.methods = {}

        for method in dir(service):
            attr = getattr(service, method)
            if ServiceMethods.is_method_accessible(method, attr):
                self.methods[method] = attr

    @staticmethod
    def is_method_accessible(name, attr):
        return callable(attr) and not name.startswith('_')


class ServiceProxy(ServiceMethods):

    name_exceptions = ['service', 'methods', 'name_exceptions', 'is_method_accessible']

    def __init__(self, service, wrap_f):
        ServiceMethods.__init__(self, service)
        for name, method in self.methods.iteritems():
            self.methods[name] = wrap_f(name, method)

    def __getattribute__(self, name, exceptions=None):
        exceptions = exceptions or ServiceProxy.name_exceptions
        if name.startswith('_') or name in exceptions:
            return ServiceMethods.__getattribute__(self, name)
        if hasattr(self, 'methods'):
            return self.methods.get(name, None)
        return None
