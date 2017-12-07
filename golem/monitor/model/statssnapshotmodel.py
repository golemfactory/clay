from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats
from .modelbase import BasicModel


class StatsSnapshotModel(BasicModel):
    def __init__(self, meta_data, known_tasks, supported_tasks, stats):
        super(StatsSnapshotModel, self).__init__(
            "Stats",
            meta_data.cliid,
            meta_data.sessid
        )

        self.known_tasks = known_tasks
        self.supported_tasks = supported_tasks
        self.computed_tasks = stats.get_stats('computed_tasks')[1]
        self.tasks_with_errors = stats.get_stats('tasks_with_errors')[1]
        self.tasks_with_timeout = stats.get_stats('tasks_with_timeout')[1]
        self.tasks_requested = stats.get_stats('tasks_requested')[1]


class VMSnapshotModel(BasicModel):
    def __init__(self, cliid, sessid, vm_snapshot):
        super(VMSnapshotModel, self).__init__("VMSnapshot", cliid, sessid)
        self.vm_snapshot = vm_snapshot


class P2PSnapshotModel(BasicModel):
    def __init__(self, cliid, sessid, p2p_snapshot):
        super(P2PSnapshotModel, self).__init__("P2PSnapshot", cliid, sessid)
        self.p2p_snapshot = p2p_snapshot


class ComputationTime(BasicModel):
    def __init__(self, meta_data, success, value):
        super(ComputationTime, self).__init__(
            "ComputationTime",
            meta_data.cliid,
            meta_data.sessid
        )
        self.success = success
        self.value = value

class RequestorStatsModel(BasicModel):
    # pylint: disable=too-many-instance-attributes,too-few-public-methods
    def __init__(self, meta_data: BasicModel, current_stats: CurrentStats,
                 finished_stats: FinishedTasksStats):
        super().__init__("RequestorStats", meta_data.cliid, meta_data.sessid)

        self.tasks_cnt = current_stats.tasks_cnt
        self.finished_task_cnt = current_stats.finished_task_cnt
        self.requested_subtasks_cnt = current_stats.requested_subtasks_cnt
        self.collected_results_cnt = current_stats.collected_results_cnt
        self.verified_results_cnt = current_stats.verified_results_cnt
        self.timed_out_subtasks_cnt = current_stats.timed_out_subtasks_cnt
        self.not_downloadable_subtasks_cnt = (current_stats
                                              .not_downloadable_subtasks_cnt)
        self.failed_subtasks_cnt = current_stats.failed_subtasks_cnt
        self.work_offers_cnt = current_stats.work_offers_cnt

        self.finished_ok_cnt = finished_stats.finished_ok.tasks_cnt
        self.finished_ok_total_time = finished_stats.finished_ok.total_time

        self.finished_with_failures_cnt = (finished_stats
                                           .finished_with_failures.tasks_cnt)
        self.finished_with_failures_total_time = (finished_stats
                                                  .finished_with_failures
                                                  .total_time)

        self.failed_cnt = finished_stats.failed.tasks_cnt
        self.failed_total_time = finished_stats.failed.total_time
