import datetime
import threading
import logging
import pickle
import os
from collections import Counter

import pytz

from golem.core.common import get_timestamp_utc
from golem.environments.environment import UnsupportReason
from golem.core import golem_async
from golem.appconfig import TASKARCHIVE_FILENAME, TASKARCHIVE_NUM_INTERVALS, \
    TASKARCHIVE_MAX_TASKS

log = logging.getLogger('golem.task.taskarchiver')


class TaskArchiver(object):
    """Utility that archives information on unsupported task reasons and
    other related task statistics. See get_unsupport_reasons() function.
    :param datadir: Directory to save the archive to
    :param max_tasks: Maximum number of non-expired tasks stored in task
                      archive at any moment
    """

    def __init__(self, datadir=None, max_tasks=TASKARCHIVE_MAX_TASKS):
        self._input_lock = threading.Lock()
        self._input_tasks = []
        self._input_statuses = []
        self._archive_lock = threading.Lock()
        self._file_lock = threading.Lock()
        self._archive = Archive()
        self._dump_file = None
        self._max_tasks = max_tasks
        log.debug('Starting taskarchiver in dir: %r', datadir)
        if datadir:
            try:
                self._dump_file = os.path.join(datadir, TASKARCHIVE_FILENAME)
                with open(self._dump_file, 'rb') as f:
                    archive = pickle.load(f)
                if archive.class_version == Archive.CLASS_VERSION:
                    self._archive = archive
                else:
                    log.info("Task archive not loaded: unsupported version: "
                             "%s", archive.class_version)
            except (EOFError, IOError, pickle.UnpicklingError) as e:
                log.info("Task archive not loaded: %s", str(e))

    def add_task(self, task_header):
        """Schedule a task to be archived.
        :param task_header: Header of task to be archived
        """
        with self._input_lock:
            self._input_tasks.append(ArchTask(task_header))

    def add_support_status(self, uuid, support_status):
        """Schedule support status of a task to be archived.
        :param uuid: Identifier of task the status belongs to
        :param support_status: SupportStatus object denoting the status
        """
        with self._input_lock:
            self._input_statuses.append((uuid, support_status))

    def do_maintenance(self):
        """Updates information on unsupported task reasons and
        other related task statistics by consuming tasks and support statuses
        scheduled for processing by add_task() and add_support_status()
        functions. Optimizes internal structures and, if needed, writes the
        entire structure to a file.
        """
        with self._input_lock:
            input_tasks, self._input_tasks = self._input_tasks, []
            input_statuses, self._input_statuses = self._input_statuses, []
        with self._archive_lock:
            ntasks_to_take = self._max_tasks - len(self._archive.tasks)
            if ntasks_to_take < len(input_tasks):
                log.warning("Maximum number of current tasks exceeded.")
            input_tasks = input_tasks[:ntasks_to_take]
            for tsk in input_tasks:
                self._archive.tasks[tsk.uuid] = tsk
            for (uuid, status) in input_statuses:
                if uuid in self._archive.tasks:
                    if UnsupportReason.REQUESTOR_TRUST in status.desc:
                        self._archive.tasks[uuid].requesting_trust = \
                            status.desc[UnsupportReason.REQUESTOR_TRUST]
                    self._archive.tasks[uuid].unsupport_reasons = \
                        list(status.desc.keys())
            cur_time = get_timestamp_utc()
            for tsk in list(self._archive.tasks.values()):
                if cur_time > tsk.deadline:
                    self._merge_to_interval(tsk)
                    del self._archive.tasks[tsk.uuid]
            self._purge_old_intervals()
            if self._dump_file:
                request = golem_async.AsyncRequest(self._dump_archive)
                golem_async.async_run(
                    request,
                    None,
                    lambda e: log.info("Dumping archive failed: %s", e),
                )

    def _dump_archive(self):
        with self._archive_lock:
            data = pickle.dumps(self._archive)
        with self._file_lock:
            with open(self._dump_file, 'wb') as f:
                f.write(data)

    def _merge_to_interval(self, tsk):
        day = tsk.interval_start_date
        if day not in self._archive.intervals:
            self._archive.intervals[day] = TimeInterval(day)
        interval = self._archive.intervals[day]
        interval.merge_task(tsk)

    def _purge_old_intervals(self):
        today = datetime.datetime.now(pytz.utc) \
            .replace(hour=0, minute=0, second=0, microsecond=0)
        old = today - datetime.timedelta(days=TASKARCHIVE_NUM_INTERVALS)
        for interval in list(self._archive.intervals.values()):
            if interval.start_date <= old:
                del self._archive.intervals[interval.start_date]

    def get_unsupport_reasons(self, last_n_days, today=None):
        """
        :param last_n_days: For how many recent calendar days (UTC timezone)
         the statistics should be computed.
        :param today: Assume today is a given date
        :return: list of dictionaries of the form {'reason': reason_type,
         'ntasks': task_count, 'avg': avg} where reason_type is one of
         unsupport reason types, task_count is the number of tasks
         affected with that reason, and avg (if available) is the most typical
         corresponding value.  For unsupport reason
         MAX_PRICE avg is the average price of all tasks observed in the network
         in the given interval. For unsupport reason APP_VERSION avg is
         the most popular app version of all tasks observed in the network
         in the given interval. For unsupport reason
         REQUESTING_TRUST avg is the average trust of all requestors that this
         node tried to process tasks for where that trust was not high enough.
         Note: number of unsupported tasks returned for a given period can
         decrease with time when these tasks become supported for some reason.
         For each task we only take into consideration the most recent support
         status of this task.
        """
        with self._archive_lock:
            return self._get_unsupport_reasons(last_n_days, today)

    def _get_unsupport_reasons(self, last_n_days, today):
        if not today:
            today = datetime.datetime.now(pytz.utc)
        today = today.replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today - datetime.timedelta(days=last_n_days-1)
        result = TimeInterval(start_date)
        result.cnt_unsupport_reasons = Counter({r: 0 for r in UnsupportReason})
        for interval in self._archive.intervals.values():
            if interval.start_date >= start_date:
                result.merge_interval(interval)
        for tsk in self._archive.tasks.values():
            if tsk.interval_start_date >= start_date:
                result.merge_task(tsk)
        ret = []
        for (reason, count) in result.cnt_unsupport_reasons.most_common():
            if reason == UnsupportReason.MAX_PRICE and result.num_tasks:
                avg = int(result.sum_max_price / result.num_tasks)
            elif reason == UnsupportReason.APP_VERSION and \
                    result.cnt_min_version:
                avg = result.cnt_min_version.most_common(1)[0][0]
            elif reason == UnsupportReason.REQUESTOR_TRUST and \
                    result.num_requesting_trust:
                avg = result.sum_requesting_trust / result.num_requesting_trust
            else:
                avg = None
            ret.append({'reason': reason.value, 'ntasks': count, 'avg': avg})
        return ret


class Archive(object):
    CLASS_VERSION = 1

    def __init__(self):
        self.class_version = Archive.CLASS_VERSION
        self.tasks = {}
        self.intervals = {}


class ArchTask(object):
    """All known tasks that have not been aggregated yet."""
    def __init__(self, task_header):
        self.uuid = task_header.task_id
        self.interval_start_date = datetime.datetime.now(pytz.utc)\
            .replace(hour=0, minute=0, second=0, microsecond=0)
        self.deadline = task_header.deadline
        self.min_version = task_header.min_version
        self.max_price = task_header.max_price
        self.requesting_trust = None
        self.unsupport_reasons = None


class TimeInterval(object):
    """Aggregate information on tasks belonging to a time interval."""
    def __init__(self, start_date):
        self.start_date = start_date
        self.sum_max_price = 0
        self.cnt_min_version = Counter()
        self.num_tasks = 0
        self.sum_requesting_trust = 0.0
        self.num_requesting_trust = 0
        self.cnt_unsupport_reasons = Counter()

    def merge_task(self, tsk):
        self.sum_max_price += tsk.max_price
        self.cnt_min_version[tsk.min_version] += 1
        self.num_tasks += 1
        self.cnt_unsupport_reasons.update(tsk.unsupport_reasons)
        if tsk.requesting_trust:
            self.sum_requesting_trust += tsk.requesting_trust
            self.num_requesting_trust += 1

    def merge_interval(self, interval):
        self.sum_max_price += interval.sum_max_price
        self.cnt_min_version.update(interval.cnt_min_version)
        self.num_tasks += interval.num_tasks
        self.sum_requesting_trust += interval.sum_requesting_trust
        self.num_requesting_trust += interval.num_requesting_trust
        self.cnt_unsupport_reasons.update(interval.cnt_unsupport_reasons)
