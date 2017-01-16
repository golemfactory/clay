from golem.ranking.helper.trust import Trust
from golem.ranking.manager import database_manager as dm
from golem.testutils import DatabaseFixture
from mock import patch


class TestDatabaseManager(DatabaseFixture):
    def test_should_update_database_records(self):
        """Should update database records
        for COMPUTED increase, decrease;
        WRONG_COMPUTED decrease;
        REQUESTED increase, decrease;
        PAYMENT increase, decrease;
        and RESOURCE increase, decrease
        using database_manager methods as well as Trust enums.
        Should create two nodes: alpha and beta.
        """
        cases = (
            # COMPUTED increase
            {'test_no': '01',
             'fun_ref': dm.increase_positive_computed,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.5,
             'attribute': 'positive_computed'
             },
            {'test_no': '02',
             'fun_ref': dm.increase_positive_computed,
             'node_name': 'alpha',
             'value': 0.7,
             'total': 1.2,
             'attribute': 'positive_computed'
             },
            {'test_no': '03',
             'fun_ref': Trust.COMPUTED.increase,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 1.5,
             'attribute': 'positive_computed'
             },
            # COMPUTED decrease
            {'test_no': '04',
             'fun_ref': Trust.COMPUTED.decrease,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 0.3,
             'attribute': 'negative_computed'
             },
            {'test_no': '05',
             'fun_ref': Trust.COMPUTED.decrease,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.8,
             'attribute': 'negative_computed'
             },
            {'test_no': '06',
             'fun_ref': dm.increase_negative_computed,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 1.3,
             'attribute': 'negative_computed'
             },
            {'test_no': '07',
             'fun_ref': dm.increase_negative_computed,
             'node_name': 'beta',
             'value': 0.4,
             'total': 0.4,
             'attribute': 'negative_computed'
             },
            {'test_no': '08',
             'fun_ref': dm.increase_negative_computed,
             'node_name': 'alpha',
             'value': 0.1,
             'total': 1.4,
             'attribute': 'negative_computed'
             },
            # WRONG_COMPUTED decrease
            {'test_no': '09',
             'fun_ref': Trust.WRONG_COMPUTED.decrease,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 0.3,
             'attribute': 'wrong_computed'
             },
            {'test_no': '10',
             'fun_ref': Trust.WRONG_COMPUTED.decrease,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.8,
             'attribute': 'wrong_computed'
             },
            {'test_no': '11',
             'fun_ref': dm.increase_wrong_computed,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 1.3,
             'attribute': 'wrong_computed'
             },
            # REQUESTED increase
            {'test_no': '12',
             'fun_ref': Trust.REQUESTED.increase,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 0.3,
             'attribute': 'positive_requested'
             },
            {'test_no': '13',
             'fun_ref': Trust.REQUESTED.increase,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.8,
             'attribute': 'positive_requested'
             },
            {'test_no': '14',
             'fun_ref': dm.increase_positive_requested,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 1.3,
             'attribute': 'positive_requested'
             },
            # REQUESTED decrease
            {'test_no': '15',
             'fun_ref': Trust.REQUESTED.decrease,
             'node_name': 'alpha',
             'value': 0.2,
             'total': 0.2,
             'attribute': 'negative_requested'
             },
            {'test_no': '16',
             'fun_ref': Trust.REQUESTED.decrease,
             'node_name': 'alpha',
             'value': 0.1,
             'total': 0.3,
             'attribute': 'negative_requested'
             },
            {'test_no': '17',
             'fun_ref': dm.increase_negative_requested,
             'node_name': 'alpha',
             'value': 1.5,
             'total': 1.8,
             'attribute': 'negative_requested'
             },
            # PAYMENT increase
            {'test_no': '18',
             'fun_ref': Trust.PAYMENT.increase,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 0.3,
             'attribute': 'positive_payment'
             },
            {'test_no': '19',
             'fun_ref': Trust.PAYMENT.increase,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.8,
             'attribute': 'positive_payment'
             },
            {'test_no': '20',
             'fun_ref': dm.increase_positive_payment,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 1.3,
             'attribute': 'positive_payment'
             },
            {'test_no': '21',
             'fun_ref': dm.increase_positive_payment,
             'node_name': 'alpha',
             'value': 0.8,
             'total': 2.1,
             'attribute': 'positive_payment'
             },
            # PAYMENT decrease
            {'test_no': '22',
             'fun_ref': Trust.PAYMENT.decrease,
             'node_name': 'alpha',
             'value': 0.2,
             'total': 0.2,
             'attribute': 'negative_payment'
             },
            {'test_no': '23',
             'fun_ref': Trust.PAYMENT.decrease,
             'node_name': 'alpha',
             'value': 0.1,
             'total': 0.3,
             'attribute': 'negative_payment'
             },
            {'test_no': '24',
             'fun_ref': dm.increase_negative_payment,
             'node_name': 'alpha',
             'value': 1.5,
             'total': 1.8,
             'attribute': 'negative_payment'
             },
            # RESOURCE increase
            {'test_no': '25',
             'fun_ref': Trust.RESOURCE.increase,
             'node_name': 'alpha',
             'value': 0.3,
             'total': 0.3,
             'attribute': 'positive_resource'
             },
            {'test_no': '26',
             'fun_ref': Trust.RESOURCE.increase,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 0.8,
             'attribute': 'positive_resource'
             },
            {'test_no': '27',
             'fun_ref': dm.increase_positive_resource,
             'node_name': 'alpha',
             'value': 0.5,
             'total': 1.3,
             'attribute': 'positive_resource'
             },
            {'test_no': '28',
             'fun_ref': dm.increase_positive_resource,
             'node_name': 'alpha',
             'value': 0.8,
             'total': 2.1,
             'attribute': 'positive_resource'
             },
            # RESOURCE decrease
            {'test_no': '29',
             'fun_ref': Trust.RESOURCE.decrease,
             'node_name': 'alpha',
             'value': 0.2,
             'total': 0.2,
             'attribute': 'negative_resource'
             },
            {'test_no': '30',
             'fun_ref': Trust.RESOURCE.decrease,
             'node_name': 'alpha',
             'value': 0.1,
             'total': 0.3,
             'attribute': 'negative_resource'
             },
            {'test_no': '31',
             'fun_ref': dm.increase_negative_resource,
             'node_name': 'alpha',
             'value': 1.5,
             'total': 1.8,
             'attribute': 'negative_resource'
             }
        )

        for case in cases:
            case['fun_ref'](case['node_name'], case['value'])
            self.assertAlmostEqual(getattr(dm.get_local_rank(case['node_name']), case['attribute']), case['total'],
                                   7, "Test no. " + case['test_no'] + " failed.")

        for node in dm.get_local_rank_for_all():
            self.assertTrue(node.node_id in ['alpha', 'beta'])

    def test_should_throw_exception_for_wrong_computed_increase(self):
        """Should throw exception when WRONG_COMPUTED is being increased."""
        with self.assertRaises(KeyError):
            Trust.WRONG_COMPUTED.increase('alpha', 0.3)

    def test_should_insert_and_update_global_rank(self):
        """Should insert and update global rank for alpha and beta nodes."""
        self.assertIsNone(dm.get_global_rank("alpha"))

        dm.upsert_global_rank("alpha", 0.3, 0.2, 1.0, 1.0)
        dm.upsert_global_rank("beta", -0.1, -0.2, 0.9, 0.8)
        dm.upsert_global_rank("alpha", 0.4, 0.1, 0.8, 0.7)

        gr = dm.get_global_rank("alpha")
        self.assertEqual(gr.computing_trust_value, 0.4)
        self.assertEqual(gr.requesting_trust_value, 0.1)
        self.assertEqual(gr.gossip_weight_computing, 0.8)
        self.assertEqual(gr.gossip_weight_requesting, 0.7)

        gr = dm.get_global_rank("beta")
        self.assertEqual(gr.computing_trust_value, -0.1)
        self.assertEqual(gr.requesting_trust_value, -0.2)
        self.assertEqual(gr.gossip_weight_computing, 0.9)
        self.assertEqual(gr.gossip_weight_requesting, 0.8)

    @patch("logging.Logger.warning")
    def test_should_insert_and_update_neighbour_rank(self, log):
        """Should insert and update neighbour local rank for alpha and beta nodes.
        Should be resistant for update by the a node itself."""
        dm.upsert_neighbour_loc_rank("alpha", "alpha", (0.5, -0.2))
        log.assert_called_with("Removing alpha self trust")

        self.assertIsNone(dm.get_neighbour_loc_rank("alpha", "beta"))

        dm.upsert_neighbour_loc_rank("alpha", "beta", (0.2, 0.3))
        nr = dm.get_neighbour_loc_rank("alpha", "beta")
        self.assertEqual(nr.node_id, "alpha")
        self.assertEqual(nr.about_node_id, "beta")
        self.assertEqual(nr.computing_trust_value, 0.2)
        self.assertEqual(nr.requesting_trust_value, 0.3)

        dm.upsert_neighbour_loc_rank("beta", "alpha", (0.5, -0.2))
        dm.upsert_neighbour_loc_rank("alpha", "beta", (-0.3, 0.9))
        nr = dm.get_neighbour_loc_rank("alpha", "beta")
        self.assertEqual(nr.node_id, "alpha")
        self.assertEqual(nr.about_node_id, "beta")
        self.assertEqual(nr.computing_trust_value, -0.3)
        self.assertEqual(nr.requesting_trust_value, 0.9)
        nr = dm.get_neighbour_loc_rank("beta", "alpha")
        self.assertEqual(nr.node_id, "beta")
        self.assertEqual(nr.about_node_id, "alpha")
        self.assertEqual(nr.computing_trust_value, 0.5)
        self.assertEqual(nr.requesting_trust_value, -0.2)

        dm.upsert_neighbour_loc_rank("alpha", "alpha", (0.5, -0.2))
        log.assert_called_with("Removing alpha self trust")
