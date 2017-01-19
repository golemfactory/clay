from threading import Thread

from mock import MagicMock

from golem.client import Client
from golem.ranking.helper.trust import Trust
from golem.ranking.manager import database_manager as dm
from golem.ranking.ranking import Ranking
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase


class TestRankingDatabase(TestWithDatabase):
    def test_local_rank(self):
        self.assertIsNone(dm.get_local_rank("ABC"))
        dm.increase_positive_computed("ABC", 2)
        lr = dm.get_local_rank("ABC")
        self.assertIsNotNone(lr)
        self.assertEqual(lr.positive_computed, 2)
        dm.increase_positive_computed("ABC", 3.5)
        dm.increase_negative_computed("DEF", 1.1)
        dm.increase_negative_computed("DEF", 1.2)
        lr = dm.get_local_rank("ABC")
        self.assertEqual(lr.positive_computed, 5.5)
        self.assertEqual(lr.negative_computed, 0.0)
        lr = dm.get_local_rank("DEF")
        self.assertEqual(lr.positive_computed, 0)
        self.assertEqual(lr.negative_computed, 2.3)
        dm.increase_wrong_computed("DEF", 10.0)
        dm.increase_wrong_computed("ABC", 3.0)
        dm.increase_wrong_computed("ABC", 0.2)
        dm.increase_positive_requested("ABC", 3.0)
        dm.increase_positive_requested("ABC", 1.1)
        dm.increase_negative_requested("ABC", 1.9)
        dm.increase_negative_requested("ABC", 0.1)
        dm.increase_positive_payment("DEF", 1)
        dm.increase_negative_payment("DEF", 2)
        dm.increase_positive_payment("DEF", 3)
        dm.increase_negative_payment("DEF", 5)
        dm.increase_positive_resource("XYZ", 7)
        dm.increase_negative_resource("XYZ", 0.4)

        lr = dm.get_local_rank("DEF")
        self.assertEqual(lr.wrong_computed, 10.0)
        self.assertEqual(lr.positive_requested, 0.0)
        self.assertEqual(lr.negative_requested, 0)
        self.assertEqual(lr.positive_payment, 4)
        self.assertEqual(lr.negative_payment, 7)
        lr = dm.get_local_rank("ABC")
        self.assertEqual(lr.wrong_computed, 3.2)
        self.assertEqual(lr.positive_requested, 4.1)
        self.assertEqual(lr.negative_requested, 2.0)
        self.assertEqual(lr.positive_payment, 0)
        self.assertEqual(lr.negative_payment, 0)
        self.assertEqual(lr.positive_resource, 0)
        self.assertEqual(lr.negative_resource, 0)
        lr = dm.get_local_rank("XYZ")
        self.assertEqual(lr.positive_resource, 7)
        self.assertEqual(lr.negative_resource, 0.4)

    def test_global_rank(self):
        self.assertIsNone(dm.get_global_rank("ABC"))
        dm.upsert_global_rank("ABC", 0.3, 0.2, 1.0, 1.0)
        dm.upsert_global_rank("DEF", -0.1, -0.2, 0.9, 0.8)
        dm.upsert_global_rank("ABC", 0.4, 0.1, 0.8, 0.7)
        gr = dm.get_global_rank("ABC")
        self.assertEqual(gr.computing_trust_value, 0.4)
        self.assertEqual(gr.requesting_trust_value, 0.1)
        self.assertEqual(gr.gossip_weight_computing, 0.8)
        self.assertEqual(gr.gossip_weight_requesting, 0.7)
        gr = dm.get_global_rank("DEF")
        self.assertEqual(gr.computing_trust_value, -0.1)
        self.assertEqual(gr.requesting_trust_value, -0.2)
        self.assertEqual(gr.gossip_weight_computing, 0.9)
        self.assertEqual(gr.gossip_weight_requesting, 0.8)

    def test_neighbour_rank(self):
        self.assertIsNone(dm.get_neighbour_loc_rank("ABC", "DEF"))
        dm.upsert_neighbour_loc_rank("ABC", "DEF", (0.2, 0.3))
        nr = dm.get_neighbour_loc_rank("ABC", "DEF")
        self.assertEqual(nr.node_id, "ABC")
        self.assertEqual(nr.about_node_id, "DEF")
        self.assertEqual(nr.computing_trust_value, 0.2)
        self.assertEqual(nr.requesting_trust_value, 0.3)
        dm.upsert_neighbour_loc_rank("DEF", "ABC", (0.5, -0.2))
        dm.upsert_neighbour_loc_rank("ABC", "DEF", (-0.3, 0.9))
        nr = dm.get_neighbour_loc_rank("ABC", "DEF")
        self.assertEqual(nr.node_id, "ABC")
        self.assertEqual(nr.about_node_id, "DEF")
        self.assertEqual(nr.computing_trust_value, -0.3)
        self.assertEqual(nr.requesting_trust_value, 0.9)
        nr = dm.get_neighbour_loc_rank("DEF", "ABC")
        self.assertEqual(nr.node_id, "DEF")
        self.assertEqual(nr.about_node_id, "ABC")
        self.assertEqual(nr.computing_trust_value, 0.5)
        self.assertEqual(nr.requesting_trust_value, -0.2)


class TestRanking(TestWithDatabase, LogTestCase):

    def test_increase_trust_thread_safety(self):
        c = MagicMock(spec=Client)
        r = Ranking(c)

        def run():
            for x in range(0, 10):
                Trust.COMPUTED.increase("ABC", 1)
                Trust.COMPUTED.decrease("ABC", 1)
                Trust.COMPUTED.increase("ABC", 1)

        thread1 = Thread(target=run)
        thread1.start()
        thread1.join()
        expected = r.get_computing_trust("ABC")
        thread1 = Thread(target=run)
        thread1.start()
        thread2 = Thread(target=run)
        thread2.start()
        thread3 = Thread(target=run)
        thread3.start()
        thread4 = Thread(target=run)
        thread4.start()
        thread1.join()
        thread2.join()
        thread3.join()
        thread4.join()
        result = r.get_computing_trust("ABC")
        self.assertEqual(result, expected)

    def test_without_reactor(self):
        r = Ranking(MagicMock(spec=Client))
        r.client.get_neighbours_degree.return_value = {'ABC': 4, 'JKL': 2, 'MNO': 5}
        r.client.collect_stopped_peers.return_value = set()
        reactor = MagicMock()
        r.run(reactor)
        assert r.reactor == reactor
        Trust.COMPUTED.increase("ABC", 1)
        Trust.REQUESTED.increase("DEF", 1)
        Trust.PAYMENT.increase("DEF", 1)
        Trust.RESOURCE.increase("GHI", 1)
        Trust.COMPUTED.decrease("DEF", 1)
        Trust.WRONG_COMPUTED.decrease("XYZ", 1)
        Trust.REQUESTED.decrease("XYZ", 1)
        Trust.REQUESTED.increase("XYZ", 1)
        Trust.PAYMENT.decrease("XYZ", 1)
        Trust.RESOURCE.decrease("DEF", 1)
        # with self.assertLogs(logger, level="WARNING"):
        #     Trust.WRONG_COMPUTED.increase("XYZ", 1)

        r._Ranking__init_stage()
        assert not r.finished
        assert not r.global_finished
        assert r.step == 0
        assert len(r.finished_neighbours) == 0
        for v in r.working_vec.values():
            assert v[0][1] == 1.0
            assert v[1][1] == 1.0
        assert r.working_vec["ABC"][0][0] > 0.0
        assert r.working_vec["ABC"][1][0] == 0.0
        assert r.working_vec["DEF"][0][0] < 0.0
        assert r.working_vec["DEF"][1][0] > 0.0
        assert r.working_vec["GHI"][0][0] == 0.0
        assert r.working_vec["GHI"][1][0] == 0.0
        assert r.working_vec["XYZ"][0][0] < 0.0
        assert r.working_vec["XYZ"][1][0] < 0.0

        assert r.prevRank["ABC"][0] > 0
        assert r.prevRank["ABC"][1] == 0
        assert r.prevRank["DEF"][0] < 0
        assert r.prevRank["DEF"][1] > 0
        assert r.prevRank["GHI"][0] == 0
        assert r.prevRank["GHI"][1] == 0
        assert r.prevRank["XYZ"][0] < 0
        assert r.prevRank["XYZ"][1] < 0

        r._Ranking__new_round()
        assert set(r.neighbours) == {'ABC', 'JKL', 'MNO'}
        assert r.k == 1
        assert r.step == 1
        assert len(r.received_gossip[0]) == 4
        found = False
        for gossip in r.received_gossip[0]:
            if gossip[0] == "DEF":
                found = True
                assert gossip[1][0][0] < 0
                assert gossip[1][0][0] > r.working_vec["DEF"][0][0]
                assert gossip[1][0][1] == 0.5
                assert gossip[1][1][0] > 0
                assert gossip[1][0][0] < r.working_vec["DEF"][1][0]
                assert gossip[1][0][1] == 0.5
        assert found
        assert r.client.send_gossip.called
        assert r.client.send_gossip.call_args[0][0] == r.received_gossip[0]
        assert r.client.send_gossip.call_args[0][1][0] in ["ABC", "JKL", "MNO"]

        r.client.collect_neighbours_loc_ranks.return_value = [['ABC', 'XYZ', [-0.2, -0.5]],
                                                              ['JKL', 'PQR', [0.8, 0.7]]]
        r.sync_network()

        r.client.collect_gossip.return_value = [[["MNO", [[0.2, 0.2], [-0.1, 0.3]]],
                                                ["ABC", [[0.3, 0.5], [0.3, 0.5]]]]]
        r._Ranking__end_round()
        assert len(r.prevRank) == 4
        assert len(r.received_gossip) == 0
        assert len(r.working_vec) == 5
        assert r.working_vec["ABC"][0][0] > r.prevRank["ABC"][0]
        assert r.working_vec["MNO"][1][0] < 0.0
        assert not r.finished
        assert not r.global_finished

        r._Ranking__make_break()
        r._Ranking__new_round()
        assert r.step == 2
        r.client.collect_gossip.return_value = []
        r._Ranking__end_round()
        assert r.finished
        r.client.send_stop_gossip.assert_called_with()
        r.client.collect_stopped_peers.return_value = {"ABC", "JKL"}
        r._Ranking__make_break()
        assert not r.global_finished
        r.client.collect_stopped_peers.return_value = {"MNO"}
        r._Ranking__make_break()
        assert r.global_finished
