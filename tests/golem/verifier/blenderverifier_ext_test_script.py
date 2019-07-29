import logging
from typing import List
import sys
import os
import traceback
import json

sys.path.insert(0,'.')

from golem.testutils import TestTaskIntegration
from golem.task.taskbase import Task
from tests.apps.blender.task.test_blenderintegration import TestBlenderIntegration
from tests.golem.verifier.test_utils.helpers import \
    find_crop_files_in_path, \
    are_pixels_equal, find_fragments_in_path


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

    def to_file(self, dir: str):
        os.makedirs(dir, exist_ok=True)

        all_path = os.path.join(dir, 'all_tests.json')
        with open(all_path, 'w') as outfile:
            json.dump(self.all_params, outfile, indent=4, sort_keys=False)

        failed_path = os.path.join(dir, 'failed_tests.json')
        with open(failed_path, 'w') as outfile:
            json.dump(self.failed_params, outfile, indent=4, sort_keys=False)

        success_path = os.path.join(dir, 'success_tests.json')
        with open(success_path, 'w') as outfile:
            json.dump(self.success_params, outfile, indent=4, sort_keys=False)


class ExtendedVerifierTestEnv():

    def __init__(self):
        self.report = Report()

    def run(self):
        parameters_sets = self._generate_parameters()
        self.run_for_params(parameters_sets)

    def run_for_params(self, parameters_sets: dict):
        logger.info("Parameters {}".format(str(parameters_sets)))

        num_sets = len(parameters_sets)
        print("Running {} parameters sets.".format(num_sets))

        for parameters_set in parameters_sets:

            try:
                tester = ExtendedVerifierTest()
                
                tester.setUp()
                tester.run_for_params_dict(parameters_set)

                self.report.success(parameters_set)

            except (Exception, RuntimeError) as e:
                _, _, tb = sys.exc_info()
                message = traceback.format_exc()
                tb_info = traceback.extract_tb(tb)
                filename, line, function, _ = tb_info[-1]

                reason = {
                    'exception' : repr(e),
                    'line' : line,
                    'filename' : filename,
                    'function' : function,
                    'stacktrace' : message,
                    'tmp_dir' : tester.tempdir
                }

                self.report.fail(parameters_set, reason)
            finally:
                self.report.update(tester.get_report())
                tester.tearDown()

            self._progress()
        
        # Add newline on end.
        print("")
        self._print_failes()
        self._reports_to_files()

    def _print_failes(self):
        print("Printing failed tests:")
        print(json.dumps(self.report.failed_params, indent=4, sort_keys=False))

    def _progress(self):
        # Print dot for each test to indicate progress like in pytest.
        print(".", end = '')

    def _reports_to_files(self):
        self.report.to_file("reports")

    def _generate_parameters(self):
        return [
            {
                'resolution' : [400, 400],
                'subtasks_count' : 2,
                'frames' : None,
                'crops_params' : {}
            },
            {
                'resolution' : [400, 400],
                'subtasks_count' : 6,
                'frames' : [1,2],
                'crops_params' : {}
            }
        ]



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
            self._assert_crops_match(task.task_definition.task_id)

        result = task.task_definition.output_file
        self.assertTrue(TestTaskIntegration.check_file_existence(result))

    def _assert_crops_match(self, task_id: str) -> None:
        task_dir = os.path.join(self.tempdir, task_id)

        try:
            crops_paths = find_crop_files_in_path(os.path.join(task_dir, 'output'))
            fragments_paths = find_fragments_in_path(os.path.join(task_dir, "work"))
        except:
            raise Exception("Can't find crop files in output or work directory.")

        assert len(crops_paths) > 0, "There were no crops produced!"
        assert len(crops_paths) == len(
            fragments_paths
        ), "Amount of rendered crops != amount of image fragments!"
        for crop_path, fragment_path in zip(
                crops_paths,
                fragments_paths,
        ):
            assert are_pixels_equal(
                crop_path,
                fragment_path,
            ), f"crop: {crop_path} doesn't match: {fragment_path}"


def run_script():
    test_env = ExtendedVerifierTestEnv()
    test_env.run()



if __name__ == "__main__":
    run_script()
