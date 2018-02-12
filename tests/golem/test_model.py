from datetime import datetime

from peewee import IntegrityError

import golem.model as m
from golem.network.p2p.node import Node
from golem.testutils import DatabaseFixture


class TestPayment(DatabaseFixture):
    def test_default_fields(self):
        p = m.Payment()
        self.assertGreaterEqual(datetime.now(), p.created_date)
        self.assertGreaterEqual(datetime.now(), p.modified_date)

    def test_create(self):
        p = m.Payment(payee="DEF", subtask="xyz", value=5,
                      status=m.PaymentStatus.awaiting)
        self.assertEqual(p.save(force_insert=True), 1)

        with self.assertRaises(IntegrityError):
            m.Payment.create(payee="DEF", subtask="xyz", value=5,
                             status=m.PaymentStatus.awaiting)
        m.Payment.create(payee="DEF", subtask="xyz2", value=4,
                         status=m.PaymentStatus.confirmed)
        m.Payment.create(payee="DEF2", subtask="xyz4", value=5,
                         status=m.PaymentStatus.sent)

        self.assertEqual(3, len([payment for payment in m.Payment.select()]))

    def test_invalid_status(self):
        with self.assertRaises(TypeError):
            m.Payment.create(payee="XX", subtask="zz", value=5, status=1)

    def test_invalid_value_type(self):
        with self.assertRaises(TypeError):
            m.Payment.create(payee="XX", subtask="float", value=5.5,
                             status=m.PaymentStatus.sent)
        with self.assertRaises(TypeError):
            m.Payment.create(payee="XX", subtask="str", value="500",
                             status=m.PaymentStatus.sent)

    def test_payment_details(self):
        p1 = m.Payment(payee="me", subtask="T1000", value=123456)
        p2 = m.Payment(payee="you", subtask="T900", value=654321)
        self.assertNotEqual(p1.payee, p2.payee)
        self.assertNotEqual(p1.subtask, p2.subtask)
        self.assertNotEqual(p1.value, p2.value)
        self.assertEqual(p1.details, m.PaymentDetails())
        self.assertEqual(p1.details, p2.details)
        self.assertIsNot(p1.details, p2.details)
        p1.details.check = True
        self.assertTrue(p1.details.check)
        self.assertEqual(p2.details.check, None)

    def test_payment_big_value(self):
        value = 10000 * 10**18
        assert value > 2**64
        m.Payment.create(payee="me", subtask="T1000", value=value,
                         status=m.PaymentStatus.sent)

    def test_payment_details_serialization(self):
        p = m.PaymentDetails(node_info=Node(node_name="bla", key="xxx"),
                             fee=700)
        dct = p.to_dict()
        self.assertIsInstance(dct, dict)
        self.assertIsInstance(dct['node_info'], dict)
        pd = m.PaymentDetails.from_dict(dct)
        self.assertIsInstance(pd.node_info, Node)
        self.assertEqual(p, pd)


class TestLocalRank(DatabaseFixture):
    def test_default_fields(self):
        r = m.LocalRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(0, r.positive_computed)
        self.assertEqual(0, r.negative_computed)
        self.assertEqual(0, r.wrong_computed)
        self.assertEqual(0, r.positive_requested)
        self.assertEqual(0, r.negative_requested)
        self.assertEqual(0, r.positive_payment)
        self.assertEqual(0, r.negative_payment)
        self.assertEqual(0, r.positive_resource)
        self.assertEqual(0, r.negative_resource)


class TestGlobalRank(DatabaseFixture):
    def test_default_fields(self):
        r = m.GlobalRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(m.NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(m.NEUTRAL_TRUST, r.computing_trust_value)
        self.assertEqual(0, r.gossip_weight_computing)
        self.assertEqual(0, r.gossip_weight_requesting)


class TestNeighbourRank(DatabaseFixture):
    def test_default_fields(self):
        r = m.NeighbourLocRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(m.NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(m.NEUTRAL_TRUST, r.computing_trust_value)


class TestTaskPreset(DatabaseFixture):
    def test_default_fields(self):
        tp = m.TaskPreset()
        assert datetime.now() >= tp.created_date
        assert datetime.now() >= tp.modified_date


class TestPerformance(DatabaseFixture):
    def test_default_fields(self):
        perf = m.Performance()
        assert datetime.now() >= perf.created_date
        assert datetime.now() >= perf.modified_date
        assert perf.value == 0.0

    def test_constraints(self):
        perf = m.Performance()
        # environment_id can't be null
        with self.assertRaises(IntegrityError):
            perf.save()

        perf.environment_id = "ENV1"
        perf.save()

        perf = m.Performance(environment_id="ENV2", value=138.18)
        perf.save()

        env1 = m.Performance.get(m.Performance.environment_id == "ENV1")
        assert env1.value == 0.0
        env2 = m.Performance.get(m.Performance.environment_id == "ENV2")
        assert env2.value == 138.18

        # environment_id must be unique
        perf3 = m.Performance(environment_id="ENV1", value=1472.11)
        with self.assertRaises(IntegrityError):
            perf3.save()

        # value doesn't have to be unique
        perf3 = m.Performance(environment_id="ENV3", value=138.18)
        perf3.save()

    def test_update_or_create(self):
        m.Performance.update_or_create("ENVX", 100)
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 100
        m.Performance.update_or_create("ENVX", 200)
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 200
        m.Performance.update_or_create("ENVXXX", 300)
        env = m.Performance.get(m.Performance.environment_id == "ENVXXX")
        assert env.value == 300
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 200
