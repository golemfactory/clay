from unittest import TestCase

from golem.network.p2p.node import Node
from golem.task.taskarchiver import TaskArchiver, Archive, ArchTask, TimeInterval
from golem.environments.environment import SupportStatus, UnsupportReason
from golem.task.taskbase import TaskHeader
from golem.core.common import timeout_to_deadline, datetime_to_timestamp
import time
import pytz
from datetime import datetime, timedelta
from uuid import uuid4


class TestTaskArchiver(TestCase):
    def setUp(self):
        self.ssok = SupportStatus.ok()
        self.ssem = SupportStatus.err(
            {UnsupportReason.ENVIRONMENT_MISSING: "env1"})
        self.sseu = SupportStatus.err(
            {UnsupportReason.ENVIRONMENT_UNSUPPORTED: "env2"})
        self.ssenat = SupportStatus.err(
            {UnsupportReason.ENVIRONMENT_NOT_ACCEPTING_TASKS: "env3"})
        self.ssmp = SupportStatus.err(
            {UnsupportReason.MAX_PRICE: "0"})
        self.ssav = SupportStatus.err(
            {UnsupportReason.APP_VERSION: "5"})
        self.ssdl = SupportStatus.err(
            {UnsupportReason.DENY_LIST: "aaa"})
        self.ssrt = SupportStatus.err(
            {UnsupportReason.REQUESTOR_TRUST: 0.5})

    def header(self, max_price, last_checking=None,
               deadline=None, min_version="4"):
        if not last_checking:
            last_checking = time.time()
        if not deadline:
            deadline = timeout_to_deadline(36000)

        ret = TaskHeader(str(uuid4()), "DEFAULT", task_owner=Node(),
                         max_price=max_price, deadline=deadline,
                         min_version=min_version)
        if last_checking:
            ret.last_checking = last_checking
        return ret

    def get_row(self, reasonsReport, unsupportReason):
        """From unsupport reasons report gets a row corresponding to given
        unsuportReason as tuple
        (ntasks, avg)"""
        for row in reasonsReport:
            if row["reason"] == unsupportReason.value:
                return (row["ntasks"], row["avg"])

    def test_empty_stats(self):
        ta = TaskArchiver()
        rep = ta.get_unsupport_reasons(5)
        for r in UnsupportReason:
            self.assertEqual(self.get_row(rep, r), (0, None))

    def test_with_remembering_tasks(self):
        ta = TaskArchiver()
        th1 = self.header(7)
        th2 = self.header(8)
        th3 = self.header(9, min_version="2")
        th4 = self.header(10)
        s1 = self.ssok
        s2 = self.ssmp.join(self.ssav)
        s3 = self.ssav.join(self.ssrt)
        s4 = self.ssok
        ta.add_task(th1)
        ta.add_task(th2)
        ta.add_task(th3)
        ta.add_task(th4)
        ta.add_support_status(th1.task_id, s1)
        ta.add_support_status(th2.task_id, s2)
        ta.add_support_status(th3.task_id, s3)
        ta.add_support_status(th4.task_id, s4)
        ta.do_maintenance()
        rep = ta.get_unsupport_reasons(5)

        def check1(report):
            self.assertEqual(self.get_row(report, UnsupportReason.APP_VERSION),
                             (2, "4"))
            self.assertEqual(self.get_row(report, UnsupportReason.DENY_LIST),
                             (0, None))
            self.assertEqual(self.get_row(report,
                                          UnsupportReason.REQUESTOR_TRUST),
                                         (1, 0.5))
            self.assertEqual(self.get_row(report, UnsupportReason.MAX_PRICE),
                             (1, (7+8+9+10)//4))
        check1(rep)
        ta.add_task(th2)
        ta.add_support_status(th2.task_id, s2)
        ta.do_maintenance()
        rep2 = ta.get_unsupport_reasons(5)
        check1(rep2)

    def test_history(self):
        ta = TaskArchiver()
        past_deadline = timeout_to_deadline(-36000)
        today = datetime.now(pytz.utc)
        back1 = today - timedelta(days=1)
        back2 = today - timedelta(days=2)
        todayts = datetime_to_timestamp(today)
        back1ts = datetime_to_timestamp(back1)
        back2ts = datetime_to_timestamp(back2)
        th1 = self.header(3, deadline=past_deadline, last_checking=back2ts)
        th2 = self.header(5, last_checking=back2ts)
        th3 = self.header(7, min_version="2", deadline=past_deadline,
                          last_checking=back2ts)
        th4 = self.header(9, last_checking=back1ts)
        th5 = self.header(11, deadline=past_deadline, last_checking=todayts)
        s1 = self.ssrt
        s2 = self.ssmp.join(self.ssav)
        s3 = self.ssav.join(self.ssrt)
        s4 = self.ssok
        s5 = self.ssmp.join(self.ssav)
        ta.add_task(th1)
        ta.add_support_status(th1.task_id, s1)
        ta.add_task(th2)
        ta.add_support_status(th2.task_id, s2)
        ta.add_task(th3)
        ta.add_task(th4)
        ta.add_support_status(th3.task_id, s3)
        ta.add_support_status(th4.task_id, s4)
        ta.do_maintenance()
        ta.add_task(th5)
        ta.add_support_status(th5.task_id, s5)
        ta.do_maintenance()
        rep = ta.get_unsupport_reasons(1, today)
        self.assertEqual(self.get_row(rep, UnsupportReason.MAX_PRICE), (1, 11))
        self.assertEqual(self.get_row(rep, UnsupportReason.APP_VERSION),
                         (1, "4"))
        self.assertEqual(self.get_row(rep, UnsupportReason.REQUESTOR_TRUST),
                         (0, None))
        rep = ta.get_unsupport_reasons(2, today)
        self.assertEqual(self.get_row(rep, UnsupportReason.MAX_PRICE), (1, 10))
        self.assertEqual(self.get_row(rep, UnsupportReason.APP_VERSION),
                         (1, "4"))
        self.assertEqual(self.get_row(rep, UnsupportReason.REQUESTOR_TRUST),
                         (0, None))
        rep = ta.get_unsupport_reasons(3, today)
        self.assertEqual(self.get_row(rep, UnsupportReason.MAX_PRICE), (2, 7))
        self.assertEqual(self.get_row(rep, UnsupportReason.APP_VERSION),
                         (3, "4"))
        self.assertEqual(self.get_row(rep, UnsupportReason.REQUESTOR_TRUST),
                         (2, 0.5))
        self.assertEqual(self.get_row(rep, UnsupportReason.DENY_LIST),
                         (0, None))
        # Re-add task that has deadline in the future - should not change the
        # report
        ta.add_task(th2)
        ta.add_support_status(th2.task_id, s2)
        ta.do_maintenance()
        rep2 = ta.get_unsupport_reasons(3, today)
        self.assertEqual(rep, rep2)
        # Re-add task that has deadline in the past - should change the
        # report as the task should have been archived
        ta.add_task(th1)
        ta.add_support_status(th1.task_id, s1)
        ta.do_maintenance()
        rep3 = ta.get_unsupport_reasons(3, today)
        self.assertNotEqual(rep, rep3)
        self.assertEqual(self.get_row(rep3, UnsupportReason.MAX_PRICE), (2, 6))
        self.assertEqual(self.get_row(rep3, UnsupportReason.APP_VERSION),
                         (3, "4"))
        self.assertEqual(self.get_row(rep3, UnsupportReason.REQUESTOR_TRUST),
                         (3, 0.5))
        self.assertEqual(self.get_row(rep3, UnsupportReason.DENY_LIST),
                         (0, None))

    def test_max_tasks(self):
        ta = TaskArchiver(max_tasks=2)
        th1 = self.header(3)
        th2 = self.header(5)
        ta.add_task(th1)
        ta.add_task(th2)
        ta.add_support_status(th1.task_id, self.ssmp)
        ta.add_support_status(th2.task_id, self.ssmp)
        ta.do_maintenance()
        rep = ta.get_unsupport_reasons(5)
        self.assertEqual(self.get_row(rep, UnsupportReason.MAX_PRICE),
                         (2, 4))
        th3 = self.header(7)
        ta.add_task(th3)
        ta.add_support_status(th3.task_id, self.ssmp)
        ta.do_maintenance()
        rep = ta.get_unsupport_reasons(5)
        self.assertEqual(self.get_row(rep, UnsupportReason.MAX_PRICE), (2, 4))
