from pathlib import Path
from typing import Dict, Any, List

from dataclasses import dataclass

TaskId = str
SubtaskId = str


@dataclass
class CreateTaskParams:
    app_id: str
    name: str
    environment: str
    task_timeout: int
    subtask_timeout: int
    output_directory: Path
    resources: List[Path]
    max_subtasks: int
    max_price_per_hour: int
    concent_enabled: bool


class RequestedTaskManager:
    def create_task(
            self,
            golem_params: CreateTaskParams,
            app_params: Dict[str, Any],
    ) -> TaskId:
        """ Creates an entry in the storage about the new task and assigns
        the task_id to it. The task then has to be initialized and started. """
        raise NotImplementedError

    def init_task(self, task_id: TaskId) -> None:
        """ Initialize the task by calling create_task on the Task API.
        The application performs validation of the params which may result in
        an error marking the task as failed. """
        raise NotImplementedError

    def start_task(self, task_id: TaskId) -> None:
        """ Marks an already initialized task as ready for computation. """
        raise NotImplementedError

    def task_exists(self, _task_id: TaskId) -> bool:  # noqa pylint: disable=no-self-use
        """ Return whether task of a given task_id exists. """
        return False

    def get_subtasks_outputs_dir(self, task_id: TaskId) -> Path:
        """ Return a path to the directory where subtasks outputs should be
        placed. """
        raise NotImplementedError

    def verify(self, task_id: TaskId, subtask_id: SubtaskId) -> bool:
        """ Return whether a subtask has been computed corectly. """
        raise NotImplementedError
