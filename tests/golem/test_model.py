from datetime import datetime

from peewee import IntegrityError
from twisted.python.failure import Failure

import golem.model as m

from golem.network.p2p.node import Node
from golem.testutils import DatabaseFixture, PEP8MixIn, TempDirFixture


class TestDatabase(TempDirFixture, PEP8MixIn):
    PEP8_FILES = ["golem/model.py"]

    def test_init(self) -> None:
        db = m.Database(self.path)
        self.assertFalse(db.is_closed())
        db.close()

    def test_schema_version(self):
        db = m.Database(self.path)
        self.assertEqual(db._get_user_version(), db.SCHEMA_VERSION)
        self.assertNotEqual(db.SCHEMA_VERSION, 0)

        db._set_user_version(0)
        self.assertEqual(db._get_user_version(), 0)
        db = m.Database(self.path)
        self.assertEqual(db._get_user_version(), db.SCHEMA_VERSION)
        db.close()


class TestPayment(DatabaseFixture):
    def test_default_fields(self):
        p = m.Payment()
        self.assertGreaterEqual(datetime.now(), p.created_date)
        self.assertGreaterEqual(datetime.now(), p.modified_date)

    def test_create(self):
        p = m.Payment(payee="DEF", subtask="xyz", value=5,
                      status=m.PaymentStatus.awaiting)
        evt = p.save(force_insert=True)
        evt.wait(10)
        assert p._get_pk_value()

        evt = m.Payment.create(payee="DEF", subtask="xyz", value=5,
                               status=m.PaymentStatus.awaiting)
        evt.wait(10)

        assert isinstance(evt.result, Failure)
        assert isinstance(evt.result.value, IntegrityError)

        m.Payment.create(payee="DEF", subtask="xyz2", value=4,
                         status=m.PaymentStatus.confirmed).wait(10)
        m.Payment.create(payee="DEF2", subtask="xyz4", value=5,
                         status=m.PaymentStatus.sent).wait(10)

        self.assertEqual(3, len([payment for payment in m.Payment.select()]))

    def test_invalid_status(self):
        evt = m.Payment.create(payee="XX", subtask="zz", value=5, status=1)
        evt.wait(10)
        # result is an instance of from twisted.python.failure import Failure
        assert isinstance(evt.result.value, TypeError)

    def test_invalid_value_type(self):
        # result is an instance of from twisted.python.failure import Failure

        evt = m.Payment.create(payee="XX", subtask="float", value=5.5,
                               status=m.PaymentStatus.sent)
        evt.wait(10)
        assert isinstance(evt.result.value, TypeError)

        m.Payment.create(payee="XX", subtask="str", value="500",
                         status=m.PaymentStatus.sent)
        evt.wait(10)
        assert isinstance(evt.result.value, TypeError)

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
        import threading
        print('>> self thread', threading.current_thread().ident)
        # environment_id can't be null
        perf = m.Performance()
        evt = perf.save()
        evt.wait(10)
        # result is an instance of from twisted.python.failure import Failure
        assert isinstance(evt.result.value, IntegrityError)

        perf.environment_id = "ENV1"
        perf.save().wait(10)

        print([x.__dict__ for x in m.Performance.select().execute()])
        print(self.database.db_service.queue.qsize())

        perf = m.Performance(environment_id="ENV2", value=138.18)
        perf.save().wait(10)

        print([x.__dict__ for x in m.Performance.select().execute()])

        env1 = m.Performance.get(m.Performance.environment_id == "ENV1")
        assert env1.value == 0.0
        env2 = m.Performance.get(m.Performance.environment_id == "ENV2")
        assert env2.value == 138.18

        # environment_id must be unique
        perf3 = m.Performance(environment_id="ENV1", value=1472.11)
        evt = perf3.save()
        evt.wait(10)
        # result is an instance of from twisted.python.failure import Failure
        assert isinstance(evt.result.value, IntegrityError)

        # value doesn't have to be unique
        perf3 = m.Performance(environment_id="ENV3", value=138.18)
        evt = perf3.save()
        evt.wait(10)
        assert not isinstance(evt.result, Failure)

    def test_update_or_create(self):
        m.Performance.update_or_create("ENVX", 100).wait(10)
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 100
        m.Performance.update_or_create("ENVX", 200).wait(10)
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 200
        m.Performance.update_or_create("ENVXXX", 300).wait(10)
        env = m.Performance.get(m.Performance.environment_id == "ENVXXX")
        assert env.value == 300
        env = m.Performance.get(m.Performance.environment_id == "ENVX")
        assert env.value == 200
