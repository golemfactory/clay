from copy import copy
from pathlib import Path
from typing import List


# pylint: disable=too-many-instance-attributes
class ComputingSubtaskStateSnapshot:
    def __init__(
            self, *,
            subtask_id: str,
            progress: float,
            seconds_to_timeout: float,
            running_time_seconds: float,
            # extra_data:
            outfilebasename: str,
            output_format: str,
            scene_file: str,
            frames: List[int],
            start_task: int,
            total_tasks: int,
            # if there's something more in extra_data, just ignore it
            **_kwargs
    ) -> None:
        self.subtask_id = subtask_id
        self.progress = progress
        self.seconds_to_timeout = seconds_to_timeout
        self.running_time_seconds = running_time_seconds
        self.outfilebasename = outfilebasename
        self.output_format = output_format
        self.scene_file = Path(scene_file).name
        self.frames = copy(frames)
        self.start_task = start_task
        self.total_tasks = total_tasks


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
