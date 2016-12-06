import uuid

from golem.rpc.router import CrossbarRouter
from golem.tools.testwithreactor import TestWithReactor


def _create_uuid_list(n=1000):
    assert n > 0
    big_chunk = []
    for i in xrange(0, n):
        big_chunk.extend(list(str(uuid.uuid4())))
    return big_chunk


# TODO: implement
class TestRPCClient(TestWithReactor):

    def setUp(self):
        self.big_chunk = _create_uuid_list()
        # self.router = CrossbarRouter()

    def tearDown(self):
        # self.router.stop()
        pass

    def test_connect(self):
        pass
