# pylint: disable=protected-access
from unittest import TestCase
from unittest.mock import Mock, patch

from pydispatch import dispatcher

from golem import testutils
from golem.task.taskrequestorstats import TaskInfo, TaskMsg, \
    RequestorTaskStats, logger, CurrentStats, TaskStats, EMPTY_TASK_STATS, \
    FinishedTasksStats, FinishedTasksSummary, RequestorTaskStatsManager, \
    EMPTY_CURRENT_STATS, EMPTY_FINISHED_STATS, AggregateTaskStats, \
    RequestorAggregateStatsManager
from golem.task.taskstate import TaskStatus, Operation, TaskOp, SubtaskOp, \
    OtherOp, SubtaskStatus, TaskState
from golem.testutils import DatabaseFixture
from golem.tools.assertlogs import LogTestCase

from tests.factories.task import taskstate as taskstate_factory


class TestTaskInfo(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        'golem/task/taskrequestorstats.py',
        'tests/golem/task/test_taskrequestorstats.py'
    ]

    def test_taskinfo_creation(self):
        # A new TaskInfo is created, it should have the status of type
        # TaskStatus.notStarted, no subtasks, and no offers of computaion
        # received
        ti = TaskInfo()
        self.assertIsNotNone(ti, "TaskInfo() returned None")
        self.assertEqual(ti.latest_status, TaskStatus.notStarted,
                         "Newly created TaskInfo should have"
                         "TaskStatus.notStarted status")
        self.assertEqual(ti.subtask_count(), 0,
                         "Newly created TaskInfo should have no subtasks")
        self.assertEqual(ti.want_to_compute_count(), 0,
                         "Newly created TaskInfo should have not received any "
                         "want to compute offers yet")

    def test_task_with_one_subtask(self):
        # Create a TaskInfo instance and let it know the task has been created
        ti = TaskInfo()
        tm = TaskMsg(ts=1.0, op=TaskOp.CREATED)
        ti.got_task_message(tm, TaskStatus.waiting)

        # latest_status got updated
        self.assertEqual(ti.latest_status, TaskStatus.waiting,
                         "TaskInfo should store the latest status supplied")
        # still no computing offers nor subtasks
        self.assertEqual(ti.subtask_count(), 0,
                         "TaskInfo should have no subtasks at this point")
        self.assertEqual(ti.want_to_compute_count(), 0,
                         "TaskInfo should have not received any want to "
                         "compute offers yet")

        # start the task
        tm = TaskMsg(ts=1.5, op=TaskOp.STARTED)
        ti.got_task_message(tm, TaskStatus.starting)

        # send a want to compute
        ti.got_want_to_compute()

        self.assertEqual(ti.want_to_compute_count(), 1,
                         "TaskInfo should have received one want to compute "
                         "offer already")

        # Create a subtask
        tm = TaskMsg(ts=2.0, op=SubtaskOp.ASSIGNED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.starting)

        # And make sure all the values are as expected
        self.assertEqual(ti.subtask_count(), 1,
                         "TaskInfo should have one subtask at this point")
        self.assertEqual(ti.collected_results_count(), 0,
                         "No results should have been collected yet")
        self.assertEqual(ti.verified_results_count(), 0,
                         "No results should have been verified yet")
        self.assertEqual(ti.not_accepted_results_count(), 0,
                         "No results should have been not accepted yet")
        self.assertEqual(ti.timeout_count(), 0,
                         "No results should have timed out yet")
        self.assertEqual(ti.not_downloaded_count(), 0,
                         "No results should have had problems w/download yet")

        self.assertGreaterEqual(ti.total_time(), 1.0,
                                "Total time should be larger than 1.0 at this "
                                "point since the task is not finished yet")
        self.assertFalse(ti.had_failures_or_timeouts(),
                         "No timeouts nor failures expected so far")
        self.assertFalse(ti.is_completed(),
                         "Task should not be considered done")
        self.assertEqual(ti.in_progress_subtasks_count(), 1,
                         "One subtask should be in progress")

        # Finish the subtask - download the results
        tm = TaskMsg(ts=3.0, op=SubtaskOp.RESULT_DOWNLOADING)
        ti.got_subtask_message("st1", tm, SubtaskStatus.downloading)

        # make sure the task is still considered active at this point
        self.assertEqual(ti.in_progress_subtasks_count(), 1,
                         "One subtask should still be in progress")
        # but the results are not downloaded
        self.assertEqual(ti.not_downloaded_count(), 1,
                         "Results of one subtask are being downloaded now")

        tm = TaskMsg(ts=4.0, op=SubtaskOp.FINISHED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.finished)

        # subtask should no longer be in progress
        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        # but it should be there anyway
        self.assertEqual(ti.subtask_count(), 1,
                         "TaskInfo should have one subtask at this point")
        # and the task should not be finished
        self.assertFalse(ti.is_completed(),
                         "Task should not be considered done")
        # we should have one subtask collected & verified, no subtasks
        # not accepted nor timeouts
        self.assertEqual(ti.collected_results_count(), 1,
                         "One result should have been collected already")
        self.assertEqual(ti.verified_results_count(), 1,
                         "One result should have been verified already")
        self.assertEqual(ti.not_accepted_results_count(), 0,
                         "No results should have been not accepted yet")
        self.assertEqual(ti.timeout_count(), 0,
                         "No results should have timed out yet")
        self.assertEqual(ti.not_downloaded_count(), 0,
                         "No results should have had problems w/download yet")

        # finally, finish the task
        tm = TaskMsg(ts=5.0, op=TaskOp.FINISHED)
        ti.got_task_message(tm, TaskStatus.finished)

        # the task should now be finished
        self.assertTrue(ti.is_completed(),
                        "Task should be considered done now")
        self.assertEqual(ti.total_time(), 4.0,
                         "Total time should equal 4.0 at this point")

    @staticmethod
    def _create_task_with_single_subtask(subtask_name="st1"):
        ti = TaskInfo()
        tm = TaskMsg(ts=1.0, op=TaskOp.CREATED)
        ti.got_task_message(tm, TaskStatus.waiting)
        tm = TaskMsg(ts=2.0, op=SubtaskOp.ASSIGNED)
        ti.got_subtask_message(subtask_name, tm, SubtaskStatus.starting)
        return ti

    def test_task_with_two_subtasks(self):
        # Create a task with a single subtask
        ti = self._create_task_with_single_subtask()

        # Create another subtask...
        tm = TaskMsg(ts=3.0, op=SubtaskOp.ASSIGNED)
        ti.got_subtask_message("st2", tm, SubtaskStatus.starting)

        self.assertEqual(ti.subtask_count(), 2,
                         "TaskInfo should have two subtasks at this point")
        self.assertEqual(ti.in_progress_subtasks_count(), 2,
                         "Both subtasks should be in progress")

        # And finish the first subtask created...
        tm = TaskMsg(ts=4.0, op=SubtaskOp.RESULT_DOWNLOADING)
        ti.got_subtask_message("st1", tm, SubtaskStatus.downloading)
        tm = TaskMsg(ts=5.0, op=SubtaskOp.FINISHED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.finished)

        # we still have one task in progress, and no downloads in progress
        self.assertEqual(ti.in_progress_subtasks_count(), 1,
                         "One subtask should still be in progress")
        self.assertEqual(ti.not_downloaded_count(), 0,
                         "No downloads should be in progress")
        # and still two subtasks...
        self.assertEqual(ti.subtask_count(), 2,
                         "TaskInfo should still have two subtasks at "
                         "this point")

        # finish the only remaining subtask
        tm = TaskMsg(ts=6.0, op=SubtaskOp.RESULT_DOWNLOADING)
        ti.got_subtask_message("st2", tm, SubtaskStatus.downloading)
        tm = TaskMsg(ts=7.0, op=SubtaskOp.FINISHED)
        ti.got_subtask_message("st2", tm, SubtaskStatus.finished)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "One subtask should still be in progress")
        self.assertEqual(ti.not_downloaded_count(), 0,
                         "No downloads should be in progress")
        self.assertEqual(ti.subtask_count(), 2,
                         "TaskInfo should still have two subtasks at "
                         "this point")
        self.assertFalse(ti.had_failures_or_timeouts(),
                         "Everything wenth smoothly so no failures were "
                         "expected")
        self.assertEqual(ti.verified_results_count(), 2,
                         "Both result should have been verified already")

    def test_task_with_various_problems(self):
        # Create a task with a single subtask
        ti = self._create_task_with_single_subtask()

        # time out the subtask...
        tm = TaskMsg(ts=3.0, op=SubtaskOp.TIMEOUT)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertEqual(ti.timeout_count(), 1,
                         "One subtask should have timed out")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have timed out")

        # create another task w/subtask and make it not pass verification
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=SubtaskOp.NOT_ACCEPTED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertEqual(ti.not_accepted_results_count(), 1,
                         "One subtask should have not been accepted")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have not been accepted")

        # and yet another that will fail on the other side
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=SubtaskOp.FAILED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)
        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have failed")

        # and a task that will time out without subtasks finished
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=TaskOp.TIMEOUT)
        ti.got_task_message(tm, TaskStatus.timeout)
        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertEqual(ti.timeout_count(), 0,
                         "No subtask should have timed out")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "Whole task should have failed")

    def test_strange_case(self):
        """An unlikely scenario, but technically not impossible.

        We create a task with a subtask, then we fail the subtask and restart
        it later on. Then we check if it is considered in progress. To be
        honest it's just for coverage.
        """
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=SubtaskOp.TIMEOUT)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        tm = TaskMsg(ts=4.0, op=SubtaskOp.RESTARTED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.restarted)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have failed")


class TestRequestorTaskStats(LogTestCase):
    def compare_task_stats(self, ts1, ts2):
        self.assertGreaterEqual(ts1.total_time, ts2.total_time)
        self.assertEqual(ts1.finished, ts2.finished)
        self.assertEqual(ts1.task_failed, ts2.task_failed)
        self.assertEqual(ts1.had_failures, ts2.had_failures)
        self.assertEqual(ts1.work_offers_cnt, ts2.work_offers_cnt)
        self.assertEqual(ts1.requested_subtasks_cnt, ts2.requested_subtasks_cnt)
        self.assertEqual(ts1.collected_results_cnt, ts2.collected_results_cnt)
        self.assertEqual(ts1.verified_results_cnt, ts2.verified_results_cnt)
        self.assertEqual(ts1.timed_out_subtasks_cnt, ts2.timed_out_subtasks_cnt)
        self.assertEqual(ts1.not_downloaded_subtasks_cnt,
                         ts2.not_downloaded_subtasks_cnt)
        self.assertEqual(ts1.failed_subtasks_cnt, ts2.failed_subtasks_cnt)

    def test_stats_collection(self):
        rs = RequestorTaskStats()

        # create a task
        tstate = TaskState()
        tstate.status = TaskStatus.notStarted
        tstate.time_started = 0.0
        rs.on_message("task1", tstate, None, TaskOp.CREATED)

        # is it finished?
        self.assertFalse(rs.is_task_finished("task1"),
                         "task1 should be in progress")
        # are the stats as expected?
        task1_ts = rs.get_task_stats("task1")
        self.compare_task_stats(task1_ts, EMPTY_TASK_STATS)

        # what about the current stats?
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 0),
                         "There should be one task only with no information "
                         "about any subtasks")

        # start the task
        tstate.status = TaskStatus.waiting
        rs.on_message("task1", tstate, op=TaskOp.STARTED)
        # still one task, no finished ones and no subtasks at all
        self.assertEqual(cs, CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 0),
                         "There should be one task only with no information "
                         "about any subtasks")

        # receive work offer
        rs.on_message("task1", tstate, op=TaskOp.WORK_OFFER_RECEIVED)
        # which does not mean that a subtask is in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 1),
                         "Got work offer now")

        # add a subtask
        tstate.subtask_states["st1"] = taskstate_factory.SubtaskState()
        sst = tstate.subtask_states["st1"]
        rs.on_message("task1", tstate, "st1", SubtaskOp.ASSIGNED)
        # a subtask in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
                         "One subtask was requested so far, otherwise there "
                         "should be no changes to stats")

        # download results of that subtask
        sst.status = SubtaskStatus.downloading
        rs.on_message("task1", tstate, "st1", SubtaskOp.RESULT_DOWNLOADING)
        # still subtask in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
                         "One subtask is still in progress, and even though "
                         "its results are being downloaded it's not shown "
                         "in the stats")

        # and finish the subtask now
        sst.status = SubtaskStatus.finished
        rs.on_message("task1", tstate, "st1", SubtaskOp.FINISHED)
        # no subtask in progress but task is still not finished
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 1, 1, 0, 0, 0, 1),
                         "Sole subtask was finished which means its results "
                         "were collected and verified")

        # send an unexpected subtask
        rs.on_message("task1", tstate, op=OtherOp.UNEXPECTED)
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 1, 1, 0, 0, 0, 1),
                         "Unexpected subtask have no influence on stats")

        # finish the task now
        tstate.status = TaskStatus.finished
        rs.on_message("task1", tstate, op=TaskOp.FINISHED)
        # no subtasks in progress, task finished
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 1, 1, 1, 1, 0, 0, 0, 1),
                         "The only task is now finished")
        self.assertTrue(rs.is_task_finished("task1"),
                        "A task should be finished now")

    @staticmethod
    def create_task_and_taskstate(rs, name):
        tstate = TaskState()
        tstate.status = TaskStatus.notStarted
        tstate.time_started = 0.0
        rs.on_message(name, tstate, op=TaskOp.CREATED)
        tstate.status = TaskStatus.waiting
        rs.on_message(name, tstate, op=TaskOp.STARTED)
        rs.on_message(name, tstate, op=TaskOp.WORK_OFFER_RECEIVED)
        return tstate

    @staticmethod
    def add_subtask(rs, task, tstate, subtask):
        tstate.subtask_states[subtask] = taskstate_factory.SubtaskState()
        rs.on_message(task, tstate, subtask, SubtaskOp.ASSIGNED)

    @staticmethod
    def finish_subtask(rs, task, tstate, subtask):
        sst = tstate.subtask_states[subtask]
        sst.status = SubtaskStatus.downloading
        rs.on_message(task, tstate, subtask, SubtaskOp.RESULT_DOWNLOADING)
        sst.status = SubtaskStatus.finished
        rs.on_message(task, tstate, subtask, SubtaskOp.FINISHED)

    @staticmethod
    def finish_task(rs, task, tstate):
        tstate.status = TaskStatus.finished
        rs.on_message(task, tstate, op=TaskOp.FINISHED)

    def test_multiple_tasks(self):
        rs = RequestorTaskStats()

        # create a task
        ts1 = self.create_task_and_taskstate(rs, "task1")
        # add two subtasks
        self.add_subtask(rs, "task1", ts1, "st1.1")
        self.add_subtask(rs, "task1", ts1, "st1.2")
        # and another task
        ts2 = self.create_task_and_taskstate(rs, "task2")
        self.add_subtask(rs, "task2", ts2, "st2.1")

        # check the stats now:
        # both tasks are not finished
        self.assertFalse(rs.is_task_finished("task1"), "task1 is still active")
        self.assertFalse(rs.is_task_finished("task2"), "task2 is still active")
        # current stats show 2 tasks, no finished tasks, 3 subtasks in progress
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(2, 0, 3, 0, 0, 0, 0, 0, 2),
                         "Two tasks should be in progress, with 3 subtasks "
                         "requested")

        # finish one of the subtasks of the first task
        self.finish_subtask(rs, "task1", ts1, "st1.1")
        self.assertFalse(rs.is_task_finished("task1"), "task1 is still active")
        self.assertFalse(rs.is_task_finished("task2"), "task2 is still active")
        # current stats show 2 tasks, no finished tasks, 2 subtasks in progress
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(2, 0, 3, 1, 1, 0, 0, 0, 2),
                         "Two tasks should be in progress, with 3 subtasks; "
                         "one subtask should be collected and verified")

        # finish task2
        self.finish_subtask(rs, "task2", ts2, "st2.1")
        self.assertFalse(rs.is_task_finished("task1"), "task1 is still active")
        self.assertFalse(rs.is_task_finished("task2"), "task2 is still active")
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(2, 0, 3, 2, 2, 0, 0, 0, 2),
                         "Two tasks should be in progress, with 3 subtasks; "
                         "two of the subtasks should be collected and verified")
        self.finish_task(rs, "task2", ts2)
        self.assertFalse(rs.is_task_finished("task1"), "task1 is still active")
        self.assertTrue(rs.is_task_finished("task2"), "task2 is finished")
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(2, 1, 3, 2, 2, 0, 0, 0, 2),
                         "One task should be in progress, with 1 subtask "
                         "running and 2 finished")

        # add a restored task with 2 subtasks
        ts3 = TaskState()
        ts3.status = TaskStatus.notStarted
        ts3.time_started = 0.0
        ts3.subtask_states["st3.1"] = taskstate_factory.SubtaskState()
        ts3.subtask_states["st3.2"] = taskstate_factory.SubtaskState()
        rs.on_message("task3", ts3, op=TaskOp.RESTORED)

        self.assertFalse(rs.is_task_finished("task1"), "task1 is still active")
        self.assertTrue(rs.is_task_finished("task2"), "task2 is finished")
        self.assertFalse(rs.is_task_finished("task3"), "task3 is still active")
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(3, 1, 5, 2, 2, 0, 0, 0, 2),
                         "2 tasks should be in progress, with 5 subtasks "
                         "(2 of them are finished)")

        # close the remaining tasks
        self.finish_subtask(rs, "task1", ts1, "st1.2")
        self.finish_task(rs, "task1", ts1)
        self.finish_subtask(rs, "task3", ts3, "st3.2")
        self.finish_subtask(rs, "task3", ts3, "st3.1")
        self.finish_task(rs, "task3", ts3)

        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(3, 3, 5, 5, 5, 0, 0, 0, 2),
                         "No tasks should be in progress, with all 5 subtasks "
                         "collected and verified")

    def test_tasks_with_errors(self):
        rs = RequestorTaskStats()
        ts1 = self.create_task_and_taskstate(rs, "task1")
        self.add_subtask(rs, "task1", ts1, "st1.1")
        self.add_subtask(rs, "task1", ts1, "st1.2")
        self.add_subtask(rs, "task1", ts1, "st1.3")
        self.add_subtask(rs, "task1", ts1, "st1.4")

        # verification failure for st1.1
        ts1.subtask_states["st1.1"].status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, "st1.1", SubtaskOp.RESULT_DOWNLOADING)
        ts1.subtask_states["st1.1"].status = SubtaskStatus.failure
        rs.on_message("task1", ts1, "st1.1", SubtaskOp.NOT_ACCEPTED)

        stats1 = rs.get_task_stats("task1")
        # Is in progress, have failed subtasks, 1 work offer, 4
        # requested subtasks, 1 collected result, no verified results,
        # no timed out subtasks, no problems with download
        self.compare_task_stats(stats1,
                                TaskStats(False, 0.0, False, True,
                                          1, 4, 1, 0, 0, 0, 0))

        # timeout for st1.2
        ts1.subtask_states["st1.2"].status = SubtaskStatus.failure
        rs.on_message("task1", ts1, "st1.2", SubtaskOp.TIMEOUT)
        # 1 timed out subtask, no other differences
        stats2 = rs.get_task_stats("task1")
        self.compare_task_stats(stats2,
                                TaskStats(False, 0.0, False, True,
                                          1, 4, 1, 0, 1, 0, 0))
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(1, 0, 4, 1, 0, 1, 0, 0, 1),
                         "1 task should be in progress with 2 subtasks, one of "
                         "them with timeout")

        # remote failure for st1.3
        ts1.subtask_states["st1.3"].status = SubtaskStatus.failure
        rs.on_message("task1", ts1, "st1.3", SubtaskOp.FAILED)
        # no changes here, but the count of subtasks in progress decreases
        stats3 = rs.get_task_stats("task1")
        self.compare_task_stats(stats3,
                                TaskStats(False, 0.0, False, True,
                                          1, 4, 1, 0, 1, 0, 1))
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(1, 0, 4, 1, 0, 1, 0, 1, 1),
                         "1 task should be in progress with 1 subtask still "
                         "running; we have one failed subtask")

        # download error for st1.4
        ts1.subtask_states["st1.4"].status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, "st1.4", SubtaskOp.RESULT_DOWNLOADING)
        # one task not downloaded
        stats4 = rs.get_task_stats("task1")
        self.compare_task_stats(stats4,
                                TaskStats(False, 0.0, False, True,
                                          1, 4, 1, 0, 1, 1, 1))
        # st1.4 may finish downloading later as the task is still in
        # progress, so we still consider st1.4 to be in progress
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(1, 0, 4, 1, 0, 1, 0, 1, 1),
                         "1 task should be in progress with 1 subtask")

        # and it should stay as download error after the task is finished
        ts1.status = TaskStatus.timeout
        rs.on_message("task1", ts1, op=TaskOp.TIMEOUT)
        stats5 = rs.get_task_stats("task1")
        self.compare_task_stats(stats5,
                                TaskStats(True, 0.0, True, True,
                                          1, 4, 1, 0, 1, 1, 1))
        # the task is finished so st1.4 won't ever finish downloading
        # so it is not in progress anymore
        self.assertEqual(rs.get_current_stats(),
                         CurrentStats(1, 1, 4, 1, 0, 1, 1, 1, 1),
                         "1 task should be finished")

    def test_resurrected_tasks(self):
        """This should probably not happen in practice, but let's test
        tasks that are finished and then modified.
        """
        rs = RequestorTaskStats()
        ts1 = self.create_task_and_taskstate(rs, "task1")
        self.add_subtask(rs, "task1", ts1, "st1.1")
        self.finish_subtask(rs, "task1", ts1, "st1.1")
        self.finish_task(rs, "task1", ts1)

        fstats1 = rs.get_finished_stats()
        ftime1 = fstats1.finished_ok.total_time
        self.assertEqual(fstats1,
                         FinishedTasksStats(
                             FinishedTasksSummary(1, ftime1),
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(0, 0.0)))

        # zombies! let's change the status to failed task
        ts1.status = TaskStatus.timeout
        rs.on_message("task1", ts1, op=TaskOp.TIMEOUT)

        fstats2 = rs.get_finished_stats()
        ftime2 = fstats2.failed.total_time
        self.assertEqual(fstats2,
                         FinishedTasksStats(
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(1, ftime2)))
        self.assertGreaterEqual(ftime2, ftime1, "Time should not go back")

        # and get it back to a good shape, create a subtask, fail it
        # and test then
        ts1.status = TaskStatus.waiting
        rs.on_message("task1", ts1, op=TaskOp.RESTARTED)
        self.add_subtask(rs, "task1", ts1, "st1.2")
        sst = ts1.subtask_states["st1.2"]
        sst.status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, "st1.2", SubtaskOp.RESULT_DOWNLOADING)
        sst.status = SubtaskStatus.failure
        rs.on_message("task1", ts1, "st1.2", SubtaskOp.NOT_ACCEPTED)
        self.finish_task(rs, "task1", ts1)

        fstats3 = rs.get_finished_stats()
        ftime3 = fstats3.finished_with_failures.total_time
        self.assertEqual(fstats3,
                         FinishedTasksStats(
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(1, ftime3),
                             FinishedTasksSummary(0, 0.0)))
        self.assertGreaterEqual(ftime3, ftime2, "Time should not go back")

        # fail it again, just for fun (and coverage)
        ts1.status = TaskStatus.aborted
        rs.on_message("task1", ts1, op=TaskOp.ABORTED)

        fstats4 = rs.get_finished_stats()
        ftime4 = fstats4.failed.total_time
        self.assertEqual(fstats4,
                         FinishedTasksStats(
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(1, ftime4)))
        self.assertGreaterEqual(ftime4, ftime3, "Time should not go back")

    def test_unknown_op(self):
        rs = RequestorTaskStats()

        tstate = TaskState()
        tstate.status = TaskStatus.notStarted
        tstate.time_started = 0.0

        class UnknownOp(Operation):
            UNKNOWN = object()

        with self.assertLogs(logger, level="DEBUG") as log:
            rs.on_message("task1", tstate, op=UnknownOp.UNKNOWN)

            assert any("Unknown operation" in l for l in log.output)

    def test_restore_finished_task(self):
        # finished task should be skipped during restore so it does not
        # clutter statistics
        rs = RequestorTaskStats()
        tstate = TaskState()
        tstate.status = TaskStatus.timeout
        tstate.time_started = 0.0

        with self.assertLogs(logger, level="DEBUG") as log:
            rs.on_message("task1", tstate, op=TaskOp.RESTORED)
            assert any("Skipping completed task" in l for l in log.output)


class TestRequestorTaskStatsManager(DatabaseFixture):
    def test_empty_stats(self):
        rtsm = RequestorTaskStatsManager()
        self.assertEqual(rtsm.get_current_stats(), EMPTY_CURRENT_STATS)
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

    def test_single_task(self):
        # Just a single task, created with one subtask and finished
        # afterwards
        rtsm = RequestorTaskStatsManager()

        tstate = TaskState()
        tstate.status = TaskStatus.notStarted
        tstate.time_started = 0.0

        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id=None,
            op=TaskOp.CREATED)

        # task created
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.status = TaskStatus.waiting
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id=None,
            op=TaskOp.STARTED)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id=None,
            op=TaskOp.WORK_OFFER_RECEIVED)

        # work offer received, but nothing more changed
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.subtask_states["st1.1"] = taskstate_factory.SubtaskState()
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            op=SubtaskOp.ASSIGNED)

        # assigned subtask reflected in stats
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.subtask_states["st1.1"].status = (
            SubtaskStatus.downloading)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            op=SubtaskOp.RESULT_DOWNLOADING)
        tstate.subtask_states["st1.1"].status = SubtaskStatus.finished
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            op=SubtaskOp.FINISHED)

        # subtask finished and verified ok
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 1, 1, 1, 0, 0, 0, 1))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.status = TaskStatus.finished
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id=None,
            op=TaskOp.FINISHED)

        # task done
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 1, 1, 1, 1, 0, 0, 0, 1))
        # duration of the task is unknown hence the complex compare
        self.assertEqual(rtsm.get_finished_stats()[0][0], 1)
        self.assertGreaterEqual(rtsm.get_finished_stats()[0][1], 0.0)
        self.assertEqual(
            rtsm.get_finished_stats()[1], FinishedTasksSummary(0, 0.0))
        self.assertEqual(
            rtsm.get_finished_stats()[2], FinishedTasksSummary(0, 0.0))

    def test_bad_message(self):
        # mostly for coverage, message without all necessary fields
        # should not cause exception nor change statistics
        rtsm = RequestorTaskStatsManager()
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id=None,
            task_state=TaskState())
        self.assertEqual(rtsm.get_current_stats(), EMPTY_CURRENT_STATS)
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)


class TestAggregateTaskStats(TestCase):

    @classmethod
    def test_init(cls):
        stats_dict = dict(
            requestor_payment_cnt=1,
            requestor_payment_delay_avg=2.0,
            requestor_payment_delay_sum=3.0,
            requestor_subtask_timeout_mag=4,
            requestor_subtask_price_mag=5,
            requestor_velocity_timeout=6,
            requestor_velocity_comp_time=7,
        )

        aggregate_stats = AggregateTaskStats(**stats_dict)

        for key, value in stats_dict.items():
            stats_value = getattr(aggregate_stats, key)
            assert isinstance(stats_value, type(value))
            assert stats_value == value


class TestRequestorAggregateStatsManager(TestCase):
    # pylint: disable=no-member

    class MockKeeper:

        def __init__(self, *_args, **_kwargs):
            self.increased_stats = dict()
            self.retrieved_stats = set()
            self.replaced_stats = dict()

            self.increase_stat = Mock(wraps=self._increase_stat)
            self.get_stats = Mock(wraps=self._get_stats)
            self.set_stat = Mock(wraps=self._set_stat)

        def _increase_stat(self, key, value):
            self.increased_stats[key] = value

        def _get_stats(self, key):
            self.retrieved_stats.add(key)
            return 0, 0

        def _set_stat(self, key, value):
            self.replaced_stats[key] = value

    def setUp(self):
        super().setUp()

        with patch('golem.task.taskrequestorstats.StatsKeeper',
                   self.MockKeeper):
            self.manager = RequestorAggregateStatsManager()

    def test_on_computed_ignored_event(self):
        self.manager._on_computed(event='ignored')
        assert not self.manager.keeper.increase_stat.called

    def test_on_computed_timeout(self):
        event_args = dict(
            subtask_count=10,
            subtask_timeout=7,
            subtask_price=10**18,
            subtask_computation_time=3600.,
            timed_out=True,
        )

        self.manager._on_computed(event='finished', **event_args)
        stats = self.manager.keeper.increased_stats

        assert stats['requestor_velocity_timeout'] == \
            event_args['subtask_computation_time']

    def test_on_computed(self):
        event_args = dict(
            subtask_count=10,
            subtask_timeout=7,
            subtask_price=10**18,
            subtask_computation_time=3600.,
        )

        self.manager._on_computed(event='finished', **event_args)
        stats = self.manager.keeper.increased_stats

        assert 'requestor_velocity_timeout' not in stats
        assert stats['requestor_subtask_timeout_mag'] != 0
        assert stats['requestor_subtask_price_mag'] != 0
        assert stats['requestor_velocity_comp_time'] != 0

    def test_on_payment_ignored_event(self):
        self.manager._on_payment(event='ignored')
        assert not self.manager.keeper.get_stats.called
        assert not self.manager.keeper.set_stat.called

    def test_on_payment(self):
        kwargs = dict(
            delay=10,
            requestor_payment_cnt=13,
            requestor_payment_delay_sum=10**3,
        )

        self.manager._on_payment(event='confirmed', **kwargs)
        retrieved = self.manager.keeper.retrieved_stats
        replaced = self.manager.keeper.replaced_stats

        assert 'requestor_payment_cnt' in retrieved
        assert 'requestor_payment_delay_sum' in retrieved

        assert replaced['requestor_payment_cnt'] != 0
        assert replaced['requestor_payment_delay_sum'] != 0
        assert replaced['requestor_payment_delay_avg'] != 0
