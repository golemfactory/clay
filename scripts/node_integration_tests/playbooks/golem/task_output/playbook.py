from datetime import datetime
from functools import partial
from pathlib import Path
import typing

from ...base import NodeTestPlaybook
from ...test_config_base import NodeId


class Playbook(NodeTestPlaybook):
    """
    This test covers:
    * Ensuring there is no output overwriting when the same task is requested
        multiple times by a single node.
    * Verifying that a separate output directory is created for every created
        task.
    * Checking whether the names of the output directories match the expected
        format (e.g. 'some_task_2019-01-01_12-00-00').
    """
    OUTPUT_DIR_TIME_FORMAT = '%Y-%m-%d_%H-%M-%S'

    def step_verify_separate_output_directories(self):
        print('Verifying task output directories.')

        task_name: str = self.task_settings_dict.get('name')
        output_contents: typing.Iterable[Path] = \
            Path(self.output_path).glob('*/*')

        for path in output_contents:
            if path.is_dir():
                try:
                    datetime.strptime(
                        path.name.strip(task_name),
                        self.OUTPUT_DIR_TIME_FORMAT
                    )
                except ValueError:
                    self.fail(f'Output directory: {path.resolve()} does not'
                              f'match the expected format.')

        self.next()

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_known_tasks,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        step_verify_separate_output_directories
    )
