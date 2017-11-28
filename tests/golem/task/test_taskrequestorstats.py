from unittest import TestCase

from pydispatch import dispatcher

from golem import testutils
from golem.task.taskrequestorstats import TaskInfo, TaskMsg, \
    RequestorTaskStats, logger, CurrentStats, TaskStats, EMPTY_TASK_STATS, \
    FinishedTasksStats, FinishedTasksSummary, RequestorTaskStatsManager, \
    EMPTY_CURRENT_STATS, EMPTY_FINISHED_STATS
from golem.task.taskstate import TaskStatus, TaskOp, SubtaskStatus, TaskState, \
    SubtaskState
from golem.tools.assertlogs import LogTestCase


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
        tm = TaskMsg(ts=1.0, op=TaskOp.TASK_CREATED)
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
        tm = TaskMsg(ts=1.5, op=TaskOp.TASK_STARTED)
        ti.got_task_message(tm, TaskStatus.starting)

        # send a want to compute
        ti.got_want_to_compute()

        self.assertEqual(ti.want_to_compute_count(), 1,
                         "TaskInfo should have received one want to compute "
                         "offer already")

        # Create a subtask
        tm = TaskMsg(ts=2.0, op=TaskOp.SUBTASK_ASSIGNED)
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
                           "Total time should be larger than 1.0 at this point "
                           "since the task is not finished yet")
        self.assertFalse(ti.had_failures_or_timeouts(),
                         "No timeouts nor failures expected so far")
        self.assertFalse(ti.is_completed(),
                         "Task should not be considered done")
        self.assertEqual(ti.in_progress_subtasks_count(), 1,
                         "One subtask should be in progress")

        # Finish the subtask - download the results
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_RESULT_DOWNLOADING)
        ti.got_subtask_message("st1", tm, SubtaskStatus.downloading)

        # make sure the task is still considered active at this point
        self.assertEqual(ti.in_progress_subtasks_count(), 1,
                         "One subtask should still be in progress")
        # but the results are not downloaded
        self.assertEqual(ti.not_downloaded_count(), 1,
                         "Results of one subtask are being downloaded now")

        tm = TaskMsg(ts=4.0, op=TaskOp.SUBTASK_FINISHED)
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
        tm = TaskMsg(ts=5.0, op=TaskOp.TASK_FINISHED)
        ti.got_task_message(tm, TaskStatus.finished)

        # the task should now be finished
        self.assertTrue(ti.is_completed(),
                        "Task should be considered done now")
        self.assertEqual(ti.total_time(), 4.0,
                         "Total time should equal 4.0 at this point")

    @staticmethod
    def _create_task_with_single_subtask(subtask_name="st1"):
        ti = TaskInfo()
        tm = TaskMsg(ts=1.0, op=TaskOp.TASK_CREATED)
        ti.got_task_message(tm, TaskStatus.waiting)
        tm = TaskMsg(ts=2.0, op=TaskOp.SUBTASK_ASSIGNED)
        ti.got_subtask_message(subtask_name, tm, SubtaskStatus.starting)
        return ti

    def test_task_with_two_subtasks(self):
        # Create a task with a single subtask
        ti = self._create_task_with_single_subtask()

        # Create another subtask...
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_ASSIGNED)
        ti.got_subtask_message("st2", tm, SubtaskStatus.starting)

        self.assertEqual(ti.subtask_count(), 2,
                         "TaskInfo should have two subtasks at this point")
        self.assertEqual(ti.in_progress_subtasks_count(), 2,
                         "Both subtasks should be in progress")

        # And finish the first subtask created...
        tm = TaskMsg(ts=4.0, op=TaskOp.SUBTASK_RESULT_DOWNLOADING)
        ti.got_subtask_message("st1", tm, SubtaskStatus.downloading)
        tm = TaskMsg(ts=5.0, op=TaskOp.SUBTASK_FINISHED)
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
        tm = TaskMsg(ts=6.0, op=TaskOp.SUBTASK_RESULT_DOWNLOADING)
        ti.got_subtask_message("st2", tm, SubtaskStatus.downloading)
        tm = TaskMsg(ts=7.0, op=TaskOp.SUBTASK_FINISHED)
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
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_TIMEOUT)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertEqual(ti.timeout_count(), 1,
                         "One subtask should have timed out")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have timed out")

        # create another task w/subtask and make it not pass verification
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_NOT_ACCEPTED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertEqual(ti.not_accepted_results_count(), 1,
                         "One subtask should have not been accepted")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have not been accepted")

        # and yet another that will fail on the other side
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_FAILED)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)
        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "One subtask should have failed")

        # and a task that will time out without subtasks finished
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=TaskOp.TASK_TIMEOUT)
        ti.got_task_message(tm, TaskStatus.timeout)
        self.assertEqual(ti.in_progress_subtasks_count(), 0,
                         "No subtasks should be in progress")
        self.assertTrue(ti.had_failures_or_timeouts(),
                        "Whole task should have failed")

    def test_strange_case(self):
        """An unlikely scenario, but technically not impossible.

        We create a task with a subtask, then we fail the subtask and restart
        it later on. Then we check if it is considered in progress. To be
        honest it's just for coverage.
        """
        ti = self._create_task_with_single_subtask()
        tm = TaskMsg(ts=3.0, op=TaskOp.SUBTASK_TIMEOUT)
        ti.got_subtask_message("st1", tm, SubtaskStatus.failure)

        tm = TaskMsg(ts=4.0, op=TaskOp.SUBTASK_RESTARTED)
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
        rs.on_message("task1", tstate, TaskOp.TASK_CREATED, None)

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
        rs.on_message("task1", tstate, TaskOp.TASK_STARTED)
        # still one task, no finished ones and no subtasks at all
        self.assertEqual(cs, CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 0),
                         "There should be one task only with no information "
                         "about any subtasks")

        # receive work offer
        rs.on_message("task1", tstate, TaskOp.WORK_OFFER_RECEIVED)
        # which does not mean that a subtask is in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 1),
                         "Got work offer now")

        # add a subtask
        tstate.subtask_states["st1"] = SubtaskState()
        sst = tstate.subtask_states["st1"]  # type: SubtaskState
        sst.subtask_status = SubtaskStatus.starting
        rs.on_message("task1", tstate, TaskOp.SUBTASK_ASSIGNED, "st1")
        # a subtask in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
                         "One subtask was requested so far, otherwise there "
                         "should be no changes to stats")

        # download results of that subtask
        sst.subtask_status = SubtaskStatus.downloading
        rs.on_message("task1", tstate, TaskOp.SUBTASK_RESULT_DOWNLOADING, "st1")
        # still subtask in progress
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1),
                         "One subtask is still in progress, and even though "
                         "its results are being downloaded it's not shown "
                         "in the stats")

        # and finish the subtask now
        sst.subtask_status = SubtaskStatus.finished
        rs.on_message("task1", tstate, TaskOp.SUBTASK_FINISHED, "st1")
        # no subtask in progress but task is still not finished
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 1, 1, 0, 0, 0, 1),
                         "Sole subtask was finished which means its results "
                         "were collected and verified")

        # send an unexpected subtask
        rs.on_message("task1", tstate, TaskOp.UNEXPECTED_SUBTASK_RECEIVED)
        cs = rs.get_current_stats()
        self.assertEqual(cs, CurrentStats(1, 0, 1, 1, 1, 0, 0, 0, 1),
                         "Unexpected subtask have no influence on stats")

        # finish the task now
        tstate.status = TaskStatus.finished
        rs.on_message("task1", tstate, TaskOp.TASK_FINISHED)
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
        rs.on_message(name, tstate, TaskOp.TASK_CREATED)
        tstate.status = TaskStatus.waiting
        rs.on_message(name, tstate, TaskOp.TASK_STARTED)
        rs.on_message(name, tstate, TaskOp.WORK_OFFER_RECEIVED)
        return tstate

    @staticmethod
    def add_subtask(rs, task, tstate, subtask):
        tstate.subtask_states[subtask] = SubtaskState()
        sst = tstate.subtask_states[subtask]
        sst.subtask_status = SubtaskStatus.starting
        rs.on_message(task, tstate, TaskOp.SUBTASK_ASSIGNED, subtask)

    @staticmethod
    def finish_subtask(rs, task, tstate, subtask):
        sst = tstate.subtask_states[subtask]
        sst.subtask_status = SubtaskStatus.downloading
        rs.on_message(task, tstate, TaskOp.SUBTASK_RESULT_DOWNLOADING,
                      subtask)
        sst.subtask_status = SubtaskStatus.finished
        rs.on_message(task, tstate, TaskOp.SUBTASK_FINISHED, subtask)

    @staticmethod
    def finish_task(rs, task, tstate):
        tstate.status = TaskStatus.finished
        rs.on_message(task, tstate, TaskOp.TASK_FINISHED)

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
        ts3.subtask_states["st3.1"] = SubtaskState()
        ts3.subtask_states["st3.1"].subtask_status = SubtaskStatus.starting
        ts3.subtask_states["st3.2"] = SubtaskState()
        ts3.subtask_states["st3.2"].subtask_status = SubtaskStatus.starting
        rs.on_message("task3", ts3, TaskOp.TASK_RESTORED)

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
        ts1.subtask_states["st1.1"].subtask_status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, TaskOp.SUBTASK_RESULT_DOWNLOADING, "st1.1")
        ts1.subtask_states["st1.1"].subtask_status = SubtaskStatus.failure
        rs.on_message("task1", ts1, TaskOp.SUBTASK_NOT_ACCEPTED, "st1.1")

        stats1 = rs.get_task_stats("task1")
        # Is in progress, have failed subtasks, 1 work offer, 4
        # requested subtasks, 1 collected result, no verified results,
        # no timed out subtasks, no problems with download
        self.compare_task_stats(stats1,
                                TaskStats(False, 0.0, False, True,
                                          1, 4, 1, 0, 0, 0, 0))

        # timeout for st1.2
        ts1.subtask_states["st1.2"].subtask_status = SubtaskStatus.failure
        rs.on_message("task1", ts1, TaskOp.SUBTASK_TIMEOUT, "st1.2")
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
        ts1.subtask_states["st1.3"].subtask_status = SubtaskStatus.failure
        rs.on_message("task1", ts1, TaskOp.SUBTASK_FAILED, "st1.3")
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
        ts1.subtask_states["st1.4"].subtask_status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, TaskOp.SUBTASK_RESULT_DOWNLOADING, "st1.4")
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
        rs.on_message("task1", ts1, TaskOp.TASK_TIMEOUT)
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
        rs.on_message("task1", ts1, TaskOp.TASK_TIMEOUT)

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
        rs.on_message("task1", ts1, TaskOp.TASK_RESTARTED)
        self.add_subtask(rs, "task1", ts1, "st1.2")
        sst = ts1.subtask_states["st1.2"]
        sst.subtask_status = SubtaskStatus.downloading
        rs.on_message("task1", ts1, TaskOp.SUBTASK_RESULT_DOWNLOADING, "st1.2")
        sst.subtask_status = SubtaskStatus.failure
        rs.on_message("task1", ts1, TaskOp.SUBTASK_NOT_ACCEPTED, "st1.2")
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
        rs.on_message("task1", ts1, TaskOp.TASK_ABORTED)

        fstats4 = rs.get_finished_stats()
        ftime4 = fstats4.failed.total_time
        self.assertEqual(fstats4,
                         FinishedTasksStats(
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(0, 0.0),
                             FinishedTasksSummary(1, ftime4)))
        self.assertGreaterEqual(ftime4, ftime3, "Time should not go back")

    def test_unknown_task_op(self):
        # for that we need to remove one of the known ops from the list
        rs = RequestorTaskStats()
        rs.UNNOTEWORTHY_OPS = []

        tstate = TaskState()
        tstate.status = TaskStatus.notStarted
        tstate.time_started = 0.0

        with self.assertLogs(logger, level="INFO") as log:
            rs.on_message("task1", tstate, TaskOp.UNEXPECTED_SUBTASK_RECEIVED)

            assert any("Unknown TaskOp" in l for l in log.output)


class TestRequestorTaskStatsManager(TestCase):
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
            task_op=TaskOp.TASK_CREATED)

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
            task_op=TaskOp.TASK_STARTED)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id=None,
            task_op=TaskOp.WORK_OFFER_RECEIVED)

        # work offer received, but nothing more changed
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.subtask_states["st1.1"] = SubtaskState()
        tstate.subtask_states["st1.1"].subtask_status = SubtaskStatus.starting
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            task_op=TaskOp.SUBTASK_ASSIGNED)

        # assigned subtask reflected in stats
        self.assertEqual(rtsm.get_current_stats(),
                         CurrentStats(1, 0, 1, 0, 0, 0, 0, 0, 1))
        self.assertEqual(rtsm.get_finished_stats(), EMPTY_FINISHED_STATS)

        tstate.subtask_states["st1.1"].subtask_status = (
            SubtaskStatus.downloading)
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            task_op=TaskOp.SUBTASK_RESULT_DOWNLOADING)
        tstate.subtask_states["st1.1"].subtask_status = SubtaskStatus.finished
        dispatcher.send(
            signal='golem.taskmanager',
            event='task_status_updated',
            task_id="task1",
            task_state=tstate,
            subtask_id="st1.1",
            task_op=TaskOp.SUBTASK_FINISHED)

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
            task_op=TaskOp.TASK_FINISHED)

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
