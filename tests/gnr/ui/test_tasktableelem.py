from unittest import TestCase

from mock import Mock

from gui.application import GNRGui
from gnr.ui.appmainwindow import AppMainWindow
from gnr.ui.tasktableelem import TaskTableElem, ItemMap


class TestTaskTableElem(TestCase):
    def setUp(self):
        super(TestTaskTableElem, self).setUp()
        self.gui = GNRGui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestTaskTableElem, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_elem(self):
        tte = TaskTableElem("TASK ID", "Finished", "TASK NAMED X")
        assert isinstance(tte, TaskTableElem)
        name = tte.get_column_item(ItemMap.Name)
        assert u"{}".format(name.text()) == u"TASK NAMED X"
        id = tte.get_column_item(ItemMap.Id)
        assert u"{}".format(id.text()) == u"TASK ID"
        status = tte.get_column_item(ItemMap.Status)
        assert u"{}".format(status.text()) == "Finished"
        time = tte.get_column_item(ItemMap.Time)
        assert u"{}".format(time.text()) == "00:00:00"
        cost = tte.get_column_item(ItemMap.Cost)
        assert u"{}".format(cost.text()) == "0.000000"
        with self.assertRaises(AssertionError):
            tte.get_column_item(ItemMap.Progress)

        assert ItemMap.count() == 6


