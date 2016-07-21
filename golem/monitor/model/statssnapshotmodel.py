from modelbase import BasicModel


class StatsSnapshotModel(BasicModel):

    def __init__(self, cliid, sessid, known_tasks, supported_tasks, computed_tasks, tasks_with_errors, tasks_with_timeout):
        super(StatsSnapshotModel, self).__init__("Stats", cliid, sessid)

        self.known_tasks = known_tasks
        self.supported_tasks = supported_tasks
        self.computed_tasks = computed_tasks
        self.tasks_with_errors = tasks_with_errors
        self.tasks_with_timeout = tasks_with_timeout


class VMSnapshotModel(BasicModel):
    def __init__(self, cliid, sessid, vm_snapshot):
        super(VMSnapshotModel, self).__init__("VMSnapshot", cliid, sessid)
        self.vm_snapshot = vm_snapshot


class P2PSnapshotModel(BasicModel):
    def __init__(self, cliid, sessid, p2p_snapshot):
        super(P2PSnapshotModel, self).__init__("P2PSnapshot", cliid, sessid)
        self.vm_snapshot = p2p_snapshot
