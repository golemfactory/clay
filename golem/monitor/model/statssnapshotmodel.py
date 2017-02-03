from modelbase import BasicModel


class StatsSnapshotModel(BasicModel):
    def __init__(self, meta_data, known_tasks, supported_tasks, stats):
        super(StatsSnapshotModel, self).__init__("Stats", meta_data.cliid, meta_data.sessid)

        self.known_tasks = known_tasks
        self.supported_tasks = supported_tasks
        self.computed_tasks = stats.get_stats('computed_tasks')[0]
        self.tasks_with_errors = stats.get_stats('tasks_with_errors')[0]
        self.tasks_with_timeout = stats.get_stats('tasks_with_timeout')[0]
        self.tasks_requested = stats.get_stats('tasks_requested')[0]


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
        super(ComputationTime, self).__init__("ComputationTime", meta_data.cliid, meta_data.sessid)
        self.success = success
        self.value = value
