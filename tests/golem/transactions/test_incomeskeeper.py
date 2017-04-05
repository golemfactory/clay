from golem.tools.testwithdatabase import TestWithDatabase
from golem.tools.assertlogs import LogTestCase
from golem.transactions.incomeskeeper import IncomesKeeper


class TestIncomesKeeper(TestWithDatabase):
    def test_init(self):
        id = IncomesDatabase()
        id.update_income("xyz", "ABC", 10, 100, IncomesState.waiting)
        ik = IncomesKeeper()
        self.assertIsInstance(ik, IncomesKeeper)
        self.assertEqual(len(ik.incomes), 1)
        self.assertEqual(ik.incomes["xyz"]["expected_value"], 100)

    def test_add_payment(self):
        ik = IncomesKeeper()
        ik.add_waiting_payment("xyz", "DEF", 10)
        ik.add_waiting_payment("zyx", "FED", 20)
        xyz = filter(lambda x: x["task"] == "xyz", ik.get_list_of_all_incomes())
        self.assertEqual(len(xyz), 1)
        self.assertEqual(xyz[0]["state"], IncomesState.waiting)
        self.assertEqual(xyz[0]["value"], 0)
        self.assertEqual(xyz[0]["expected_value"], 10)
        ik.add_timeouted_payment("xyz")
        xyz = filter(lambda x: x["task"] == "xyz", ik.get_list_of_all_incomes())
        self.assertEqual(len(xyz), 1)
        self.assertEqual(xyz[0]["state"], IncomesState.timeout)
        self.assertEqual(xyz[0]["expected_value"], 10)
        ik.add_income("xyz", "DEF", 10)
        ik.add_income("zyz", "FED", 100)
        xyz = filter(lambda x: x["task"] == "xyz", ik.get_list_of_all_incomes())
        self.assertEqual(len(xyz), 1)
        self.assertEqual(xyz[0]["state"], IncomesState.finished)
        self.assertEqual(xyz[0]["value"], 10)
        self.assertEqual(xyz[0]["expected_value"], 10)
        zyz = filter(lambda x: x["task"] == "zyz", ik.get_list_of_all_incomes())
        self.assertEqual(len(zyz), 1)
        self.assertEqual(zyz[0]["state"], IncomesState.finished)
        self.assertEqual(zyz[0]["value"], 100)
        self.assertEqual(zyz[0]["expected_value"], 0)
        ik.add_income("xyz", "DEF", 10)
        xyz = filter(lambda x: x["task"] == "xyz", ik.get_list_of_all_incomes())
        self.assertEqual(xyz[0]["state"], IncomesState.finished)
        self.assertEqual(xyz[0]["value"], 20)
        self.assertEqual(xyz[0]["expected_value"], 10)

    def test_get_income(self):
        ik = IncomesKeeper()
        self.assertIsNone(ik.get_income("ABC", 0))
        self.assertEqual(ik.get_income("ABC", 10), [])
        ik.add_waiting_payment("xyz", "ABC", 3)
        ik.add_waiting_payment("abc", "ABC", 2)
        ik.add_waiting_payment("qvu", "DEF", 1)
        ik.add_waiting_payment("def", "ABC", 10)
        self.assertEqual(ik.get_income("ABC", 10), ["xyz", "abc"])
        self.assertEqual(ik.get_income("ABC", 2), [])
        self.assertEqual(ik.get_income("ABC", 3), ["def"])
