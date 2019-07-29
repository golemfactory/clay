import logging
from typing import List
import sys

sys.path.insert(0,'.')

from golem.testutils import TestTaskIntegration
from golem.task.taskbase import Task
from tests.apps.blender.task.test_blenderintegration import TestBlenderIntegration


logger = logging.getLogger(__name__)



class Report:

    def __init__(self):
        self.failed_params: List[dict] = list()
        self.success_params: List[dict] = list()
        self.all_params: List[dict] = list()

    def success(self, params: dict) -> None:
        self.success_params.append(params)
        self.all_params.append(params)

    def fail(self, params: dict, reason: dict) -> None:
        params['fail_reason'] = reason

        self.failed_params.append(params)
        self.all_params.append(params)

    def update(self, report: 'Report') -> None:
        self.failed_params = self.failed_params + report.failed_params
        self.success_params = self.success_params + report.success_params
        self.all_params = self.all_params + report.all_params




class ExtendedVerifierTestEnv():

    def __init__(self):
        self.report = Report()

    def run(self):
        parameters_sets = self._generate_parameters()

        logger.info("Parameters {}".format(str(parameters_sets)))

        num_sets = len(parameters_sets)
        logger.info("Running {} parameters sets.".format(num_sets))

        for parameters_set in parameters_sets:

            try:
                tester = ExtendedVerifierTest()
                
                tester.setUp()
                tester.run_for_params_dict(parameters_set)

            except (Exception, RuntimeError)as e:
                logger.error("Exception ocured during testing: {}".format(repr(e)))
            finally:
                self.report.update(tester.get_report())
                tester.tearDown()

            # Print dot for each test to indicate progress like in pytest.
            print(".", end = '')
        
        # Add newline on end.
        print("")
        self._print_failes()

    def _generate_parameters(self):
        return [
            {
                'resolution' : [400, 400],
                'subtasks_count' : 2,
                'frames' : None,
                'crops_params' : {}
            }
        ]

    def _print_failes(self):
        print("Printing failed tests:")
        print(str(self.report.failed_params))




class ExtendedVerifierTest(TestBlenderIntegration):

    def __init__(self):
        super().__init__()
        self.report = Report()

    def get_report(self):
        return self.report

    def run_for_params_dict(self, parameters_set: dict):
        resolution = parameters_set['resolution']
        subtasks = parameters_set['subtasks_count']
        frames = parameters_set['frames']
        crops_params = parameters_set['crops_params']

        self.run_for_parameters_set(resolution, subtasks, frames, crops_params)

    def run_for_parameters_set(self, resolution: List[int], subtasks: int, frames: List[int], crops_params: dict):
        task_def = self._task_dictionary(scene_file=self._get_chessboard_scene(),
                                         resolution=resolution,
                                         subtasks_count=subtasks,
                                         frames=frames)

        task: Task = self.start_task(task_def)

        for i in range(task.task_definition.subtasks_count):
            result, subtask_id, _ = self.compute_next_subtask(task, i)
            self.verify_subtask(task, subtask_id, result)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))




def run_script():
    test_env = ExtendedVerifierTestEnv()
    test_env.run()



if __name__ == "__main__":
    run_script()
