import time


class TaskState:

    def __init__(self):

        self.status = TaskStatus.notStarted
        self.progress = 0.0
        self.remaining_time = 0
        self.elapsed_time = 0
        self.time_started = 0
        self.payment_booked = False
        self.payment_settled = False

        self.subtask_states = {}

        self.extra_data = {}

    def get_subtask_state(self, subtask_id):
        if subtask_id in self.subtask_states:
            return self.subtask_states[subtask_id]
        else:
            return None

    def get_subtask_state_for_computer(self, node_id):

        subtasks_states = []

        for k in self.subtask_states:
            ss = self.subtask_states[k]
            if ss.computer.node_id == node_id:
                subtasks_states.append(ss)


class ComputerState:
    def __init__(self):
        self.node_id = ""
        self.eth_account = ""
        self.performance = 0
        self.ip_address = ""
        self.port = 0
        self.node_name = ""


class SubtaskState:
    def __init__(self):
        self.subtask_definition = ""
        self.subtask_id = ""
        self.subtask_progress = 0.0
        self.time_started = 0
        self.ttl = 0
        self.last_checking = time.time()
        self.extra_data = {}
        self.subtask_rem_time = 0
        self.subtask_status = ""
        self.value = 0

        self.computer = ComputerState()


class TaskStatus:
    notStarted = "Not started"
    sending = "Sending"
    waiting = "Waiting"
    starting = "Starting"
    computing = "Computing"
    finished = "Finished"
    aborted = "Aborted"
    failure = "Failure"
    paused = "Paused"


class SubtaskStatus:
    waiting = "Waiting"
    starting = "Starting"
    resent = "Failed - Resent"
    finished = "Finished"
    failure = "Failure"
