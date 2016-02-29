import os
from datetime import datetime

from peewee import IntegrityError
from golem.model import Node, Payment, ReceivedPayment, LocalRank, GlobalRank, \
    NeighbourLocRank, NEUTRAL_TRUST, Database, DATABASE_NAME
from golem.tools.testwithdatabase import TestWithDatabase, TestDirFixture


class TestDatabase(TestDirFixture):
    def test_init(self):
        db = Database(os.path.join(self.path, "abcdef.db"))
        self.assertEqual(db.name, os.path.join(self.path, "abcdef.db"))
        self.assertFalse(db.db.is_closed())
        db.db.close()

        db = Database()
        self.assertEqual(db.name, DATABASE_NAME)
        self.assertFalse(db.db.is_closed())
        db.db.close()


class TestNode(TestWithDatabase):
    def test_default_fields(self):
        n = Node()
        self.assertGreaterEqual(datetime.now(), n.created_date)
        self.assertGreaterEqual(datetime.now(), n.modified_date)

    def test_create(self):
        with self.assertRaises(Node.DoesNotExist):
            Node.select().where(Node.node_id == "ABC").get()
        n = Node.create(node_id="ABC")
        n2 = Node.select().where(Node.node_id == "ABC").get()
        self.assertEquals(n.created_date, n2.created_date)
        self.assertEquals(n.modified_date, n2.modified_date)
        with self.assertRaises(IntegrityError):
            Node.create(node_id="ABC")
        Node.create(node_id="DEF")
        self.assertEquals(len([node for node in Node.select()]), 2)


class TestPayment(TestWithDatabase):

    def test_default_fields(self):
        p = Payment()
        self.assertGreaterEqual(datetime.now(), p.created_date)
        self.assertGreaterEqual(datetime.now(), p.modified_date)

    def test_create(self):
        p = Payment(to_node_id="DEF", task="xyz", val="5.232", state="SOMESTATE")
        self.assertEquals(p.save(force_insert=True), 1)
        with self.assertRaises(IntegrityError):
            Payment.create(to_node_id="DEF", task="xyz", val="5.132", state="SOMESTATEX")
        Payment.create(to_node_id="DEF", task="xyz2", val="5.132", state="SOMESTATEX")
        Payment.create( to_node_id="DEF2", task="xyz", val="5.132", state="SOMESTATEX")

        self.assertEqual(3, len([payment for payment in Payment.select()]))


class TestReceivedPayment(TestWithDatabase):

    def test_default_fields(self):
        r = ReceivedPayment()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)

    def test_create(self):
        r = ReceivedPayment(from_node_id="DEF", task="xyz", val="5.232", expected_val="3131.23",
                            state="SOMESTATE")
        self.assertEquals(r.save(force_insert=True), 1)
        with self.assertRaises(IntegrityError):
            ReceivedPayment.create(from_node_id="DEF", task="xyz", val="5.132", expected_val="3132.33",
                                   state="SOMESTATEX")
        ReceivedPayment.create(from_node_id="DEF", task="xyz2", val="5.132", expected_val="3132.33",
                               state="SOMESTATEX")
        ReceivedPayment.create(from_node_id="DEF2", task="xyz", val="5.132", expected_val="3132.33",
                               state="SOMESTATEX")

        self.assertEqual(3,
                         len([payment for payment in ReceivedPayment.select()]))


class TestLocalRank(TestWithDatabase):

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


class TestGlobalRank(TestWithDatabase):

    def test_default_fields(self):
        r = GlobalRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(NEUTRAL_TRUST, r.computing_trust_value)
        self.assertEqual(0, r.gossip_weight_computing)
        self.assertEqual(0, r.gossip_weight_requesting)


class TestNeighbourRank(TestWithDatabase):

    def test_default_fields(self):
        r = NeighbourLocRank()
        self.assertGreaterEqual(datetime.now(), r.created_date)
        self.assertGreaterEqual(datetime.now(), r.modified_date)
        self.assertEqual(NEUTRAL_TRUST, r.requesting_trust_value)
        self.assertEqual(NEUTRAL_TRUST, r.computing_trust_value)
