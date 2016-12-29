from unittest import TestCase

from gui.view.envtableelem import EnvTableElem


class TestEnvTableElem(TestCase):
    def test_table_elem(self):
        elem = EnvTableElem("ID1", "SUPPORTED", "SOME ENV", True)
        self.assertEqual(elem.id, "ID1")
        self.assertEqual(elem.status, "SUPPORTED")
        self.assertEqual(elem.short_description, "SOME ENV")
        self.assertTrue(elem.accept_tasks)
        self.assertEqual(elem.id_item.text(), "ID1")
        self.assertEqual(elem.status_item.text(), "SUPPORTED")
        self.assertEqual(elem.short_description_item.text(), "SOME ENV")
        self.assertIsNotNone(elem.accept_tasks_item.checkState())

        elem = EnvTableElem("ID2", "SUPPORTED TOO", "SOME ENV2", False)
        self.assertEqual(elem.id, "ID2")
        self.assertEqual(elem.status, "SUPPORTED TOO")
        self.assertEqual(elem.short_description, "SOME ENV2")
        self.assertFalse(elem.accept_tasks)
        self.assertEqual(elem.id_item.text(), "ID2")
        self.assertEqual(elem.status_item.text(), "SUPPORTED TOO")
        self.assertEqual(elem.short_description_item.text(), "SOME ENV2")
        self.assertIsNotNone(elem.accept_tasks_item.checkState())

        self.assertEqual("ID2", elem.get_column_item(0).text())
        self.assertEqual("SUPPORTED TOO", elem.get_column_item(1).text())
        self.assertIsNotNone(elem.get_column_item(2).checkState())
        self.assertEqual("SOME ENV2", elem.get_column_item(3).text())
        with self.assertRaises(ValueError):
            elem.get_column_item(4)



