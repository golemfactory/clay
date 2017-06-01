import collections

from golem.core.common import to_unicode


class TaskState(object):
    def __init__(self):
        self.status = TaskStatus.notStarted
        self.progress = 0.0
        self.remaining_time = 0
        self.elapsed_time = 0
        self.time_started = 0
        self.payment_booked = False
        self.payment_settled = False
        self.outputs = []
        self.total_subtasks = 0
        self.subtask_states = {}

        self.extra_data = {}

    def __repr__(self):
        return '<TaskStatus: %r %.2f>' % (self.status, self.progress)

    def to_dictionary(self):
        preview = self.extra_data.get('result_preview')

        if isinstance(preview, basestring):
            preview = to_unicode(preview)
        elif isinstance(preview, collections.Iterable):
            preview = [to_unicode(entry) for entry in preview]

        return {
            u'time_remaining': self.remaining_time,
            u'status': to_unicode(self.status),
            u'preview': preview
        }


class ComputerState(object):
    def __init__(self):
        self.node_id = ""
        self.eth_account = ""
        self.performance = 0
        self.ip_address = ""
        self.port = 0
        self.node_name = ""
        self.price = 0


class SubtaskState(object):
    def __init__(self):
        self.subtask_definition = ""
        self.subtask_id = ""
        self.subtask_progress = 0.0
        self.time_started = 0
        self.deadline = 0
        self.extra_data = {}
        self.subtask_rem_time = 0
        self.subtask_status = ""
        self.value = 0
        self.stdout = ""
        self.stderr = ""
        self.results = []
        self.computation_time = 0

        self.computer = ComputerState()

    def to_dictionary(self):
        return {
            u'subtask_id': to_unicode(self.subtask_id),
            u'node_name': to_unicode(self.computer.node_name),
            u'node_id': to_unicode(self.computer.node_id),
            u'node_performance': to_unicode(self.computer.performance),
            u'node_ip_address': to_unicode(self.computer.ip_address),
            u'node_port': self.computer.port,
            u'status': to_unicode(self.subtask_status),
            u'progress': self.subtask_progress,
            u'time_started': self.time_started,
            u'time_remaining': self.subtask_rem_time,
            u'results': [to_unicode(r) for r in self.results],
            u'stderr': to_unicode(self.stderr),
            u'stdout': to_unicode(self.stdout)
        }


class TaskStatus(object):
    notStarted = u"Not started"
    sending = u"Sending"
    waiting = u"Waiting"
    starting = u"Starting"
    computing = u"Computing"
    finished = u"Finished"
    aborted = u"Aborted"
    timeout = u"Timeout"
    paused = u"Paused"


class SubtaskStatus(object):
    starting = u"Starting"
    downloading = u"Downloading"
    resent = u"Failed - Resent"
    finished = u"Finished"
    failure = u"Failure"
    restarted = u"Restart"

    @classmethod
    def is_computed(cls, status):
        return status in [cls.starting, cls.downloading]


class TaskTestStatus(object):
    started = u'Started'
    success = u'Success'
    error = u'Error'
