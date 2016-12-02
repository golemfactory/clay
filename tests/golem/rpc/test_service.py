import unittest

from golem.rpc.legacy.service import ServiceHelper, ServiceMethods


class MockService(object):
    def method_1(self):
        return 1

    def method_2(self, arg):
        return str(arg)


class TestService(unittest.TestCase):

    def test_helper(self):

        service = MockService()
        methods = ServiceHelper.to_dict(service)
        method_names = ServiceHelper.to_set(service)

        assert len(method_names) == 2
        assert len(method_names) == len(methods)
        assert 'method_1' in method_names
        assert 'method_2' in method_names

        for method_name in method_names:
            assert method_name in methods

    def test_methods(self):

        service = MockService()
        _methods = ServiceMethods(service)
        _dict = ServiceHelper.to_dict(service)
        _set = ServiceHelper.to_set(service)
        _list = list(_set)

        def eq(f, s):
            return len(f) == len(s) and all([_f in s for _f in f])

        assert eq(ServiceMethods.names(service), _set)
        assert eq(ServiceMethods.names(_methods), _set)
        assert eq(ServiceMethods.names(_dict), _set)
        assert eq(ServiceMethods.names(_set), _set)
        assert eq(ServiceMethods.names(_list), _set)
