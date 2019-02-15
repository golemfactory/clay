import os
import typing

from ..base import NodeTestPlaybook


class DuplicatedFilesNames(NodeTestPlaybook):
    provider_node_script = 'provider/debug'
    requestor_node_script = 'requestor/debug'

    def step_set_task_in_creation_to_false(self):
        self.task_in_creation = False
        self.next()

    def step_verify_duplicated_output(self):
        _, __, files = os.walk(self.output_path).__next__()
        print(f'Files found in output path: {files}')
        files_count = len(files)
        if files_count == 2:
            print('Separate files created correctly.')
            self.success()
        elif files_count == 1:
            print('Output file was overwritten.')
            self.fail()
        else:
            print('There should be exactly 2 files in output path.')
            self.fail()

    steps: typing.Tuple = NodeTestPlaybook.initial_steps + (
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        NodeTestPlaybook.step_verify_output,
        NodeTestPlaybook.step_get_known_tasks,
        step_set_task_in_creation_to_false,
        NodeTestPlaybook.step_create_task,
        NodeTestPlaybook.step_get_task_id,
        NodeTestPlaybook.step_get_task_status,
        NodeTestPlaybook.step_wait_task_finished,
        step_verify_duplicated_output,
    )
