from datetime import datetime

from peewee import IntegrityError
from golem.model import (Payment, PaymentStatus, LocalRank,
                         GlobalRank, NeighbourLocRank, NEUTRAL_TRUST, Database,
                         TaskPreset, PaymentDetails)
from golem.network.p2p.node import Node
from golem.testutils import DatabaseFixture, TempDirFixture


class TestDatabase(TempDirFixture):
    def test_init(self) -> None:
        db = Database(self.path)
        self.assertFalse(db.db.is_closed())
        db.db.close()

    def test_schema_version(self):
        db = Database(self.path)
        self.assertEqual(db._get_user_version(), db.SCHEMA_VERSION)
        self.assertNotEqual(db.SCHEMA_VERSION, 0)

        db._set_user_version(0)
        self.assertEqual(db._get_user_version(), 0)
        db = Database(self.path)
        self.assertEqual(db._get_user_version(), db.SCHEMA_VERSION)
        db.db.close()


class TestPayment(DatabaseFixture):
    def test_default_fields(self):
        p = Payment()
        self.assertGreaterEqual(datetime.now(), p.created_date)
        self.assertGreaterEqual(datetime.now(), p.modified_date)

    def test_create(self):
        p = Payment(payee="DEF", subtask="xyz", value=5,
                    status=PaymentStatus.awaiting)
        self.assertEqual(p.save(force_insert=True), 1)
        with self.assertRaises(IntegrityError):
            Payment.create(payee="DEF", subtask="xyz", value=5,
                           status=PaymentStatus.awaiting)
        Payment.create(payee="DEF", subtask="xyz2", value=4,
                       status=PaymentStatus.confirmed)
        Payment.create(payee="DEF2", subtask="xyz4", value=5,
                       status=PaymentStatus.sent)

        self.assertEqual(3, len([payment for payment in Payment.select()]))

    def test_invalid_status(self):
        with self.assertRaises(TypeError):
            Payment.create(payee="XX", subtask="zz", value=5, status=1)

    def test_invalid_value_type(self):
        with self.assertRaises(TypeError):
            Payment.create(payee="XX", subtask="float", value=5.5,
                           status=PaymentStatus.sent)
        with self.assertRaises(TypeError):
            Payment.create(payee="XX", subtask="str", value="500",
                           status=PaymentStatus.sent)

    def test_payment_details(self):
        p1 = Payment(payee="me", subtask="T1000", value=123456)
        p2 = Payment(payee="you", subtask="T900", value=654321)
        self.assertNotEqual(p1.payee, p2.payee)
        self.assertNotEqual(p1.subtask, p2.subtask)
        self.assertNotEqual(p1.value, p2.value)
        self.assertEqual(p1.details, PaymentDetails())
        self.assertEqual(p1.details, p2.details)
        self.assertIsNot(p1.details, p2.details)
        p1.details.check = True
        self.assertTrue(p1.details.check)
        self.assertEqual(p2.details.check, None)

    def test_payment_big_value(self):
        value = 10000 * 10 ** 18
        assert value > 2 ** 64
        Payment.create(payee="me", subtask="T1000", value=value,
                       status=PaymentStatus.sent)

    def test_payment_details_serialization(self):
        p = PaymentDetails(node_info=Node(node_name="bla", key="xxx"), fee=700)
        dct = p.to_dict()
        self.assertIsInstance(dct, dict)
        self.assertIsInstance(dct['node_info'], dict)
        pd = PaymentDetails.from_dict(dct)
        self.assertIsInstance(pd.node_info, Node)
        self.assertEqual(p, pd)


class TestLocalRank(DatabaseFixture):
    def test_default_fields(self):
        r = LocalRank()
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
        r = GlobalRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(NEUTRAL_TRUST, r.computing_trust_value)
        self.assertEqual(0, r.gossip_weight_computing)
        self.assertEqual(0, r.gossip_weight_requesting)


class TestNeighbourRank(DatabaseFixture):
    def test_default_fields(self):
        r = NeighbourLocRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(NEUTRAL_TRUST, r.computing_trust_value)


class TestTaskPreset(DatabaseFixture):
    def test_default_fields(self):
        tp = TaskPreset()
        assert datetime.now() >= tp.created_date
        assert datetime.now() >= tp.modified_date
