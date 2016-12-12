from unittest import TestCase

from gui.view.envtableelem import EnvTableElem


class TestEnvTableElem(TestCase):
    def test_table_elem(self):
        elem = EnvTableElem("ID1", "SUPPORTED", "SOME ENV", True)
        assert elem.id == "ID1"
        assert elem.status == "SUPPORTED"
        assert elem.short_description == "SOME ENV"
        assert elem.accept_tasks
        assert elem.id_item.text() == "ID1"
        assert elem.status_item.text() == "SUPPORTED"
        assert elem.short_description_item.text() == "SOME ENV"
        assert elem.accept_tasks_item.checkState()

        elem = EnvTableElem("ID2", "SUPPORTED TOO", "SOME ENV2", False)
        assert elem.id == "ID2"
        assert elem.status == "SUPPORTED TOO"
        assert elem.short_description == "SOME ENV2"
        assert not elem.accept_tasks
        assert elem.id_item.text() == "ID2"
        assert elem.status_item.text() == "SUPPORTED TOO"
        assert elem.short_description_item.text() == "SOME ENV2"
        assert not elem.accept_tasks_item.checkState()

        assert "ID2" == elem.get_column_item(0).text()
        assert "SUPPORTED TOO" == elem.get_column_item(1).text()
        assert not elem.get_column_item(2).checkState()
        assert "SOME ENV2" == elem.get_column_item(3).text()
        with self.assertRaises(AssertionError):
            elem.get_column_item(4)



