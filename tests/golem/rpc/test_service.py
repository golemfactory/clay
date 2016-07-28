import unittest

from golem.rpc.service import ServiceProxy


class MockService(object):
    def method_1(self):
        return 1

    def method_2(self, arg):
        return str(arg)


class MockServiceProxy(ServiceProxy):
    def wrap(self, name, method):
        return method


class TestServiceProxy(unittest.TestCase):

    def test(self):

        service = MockService()

        with self.assertRaises(NotImplementedError):
            ServiceProxy(service)

        proxy = MockServiceProxy(service)

        assert proxy.method_1 is not None
        assert proxy.method_3 is None
        assert proxy.method_1() == 1
        assert proxy.method_2(123.45) == '123.45'
