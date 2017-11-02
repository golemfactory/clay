from datetime import datetime


class TaskChunkStateSnapshot:
    def __init__(self, chunk_id, cpu_power, est_time_left, progress, chunk_short_desc):
        self.chunk_id = chunk_id
        self.cpu_power = cpu_power
        self.est_time_left = est_time_left
        self.progress = progress
        self.chunk_short_desc = chunk_short_desc

    def get_chunk_id(self):
        return self.chunk_id

    def get_cpu_power(self):
        return self.cpu_power

    def get_estimated_time_left(self):
        return self.est_time_left

    def get_progress(self):
        return self.progress

    def get_chunk_short_descr(self):
        return self.chunk_short_desc


class LocalTaskStateSnapshot:
    def __init__(self, task_id, total_tasks, active_tasks, progress, task_short_desc):
        self.task_id = task_id
        self.total_tasks = total_tasks
        self.active_tasks = active_tasks
        self.progress = progress
        self.task_short_desc = task_short_desc

    def get_task_id(self):
        return self.task_id

    def get_total_tasks(self):
        return self.total_tasks

    def get_active_tasks(self):
        return self.active_tasks

    def get_progress(self):
        return self.progress

    def get_task_short_desc(self):
        return self.task_short_desc
