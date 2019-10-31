import copy
import json
import logging
import os
import sys
import traceback
from typing import List

from golem.task.taskbase import Task
from tests.apps.blender.task.test_blenderintegration import \
    TestBlenderIntegration
from tests.golem.verifier.test_utils.helpers import \
    find_crop_files_in_path, \
    are_pixels_equal, find_fragments_in_path

logger = logging.getLogger(__name__)
logging.disable(logging.CRITICAL)


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

    # Merge reports with the same parameters but different crops.
    # Note: This function doesn't check if reports have the same parameters.
    def merge_reports_content(self):
        if self.failed_params:
            self.failed_params = [self.merge_report(self.failed_params)]
        if self.all_params:
            self.all_params = [self.merge_report(self.all_params)]
        if self.success_params:
            self.success_params = [self.merge_report(self.success_params)]

    def merge_report(self, report: List[dict]):
        if report:
            # Choose one report and copy common part.
            report_params = copy.deepcopy(report[0])

            # Delete parameters and replace it with empty dict.
            # It will be updated below.
            del report_params['crops_params']
            report_params['crops_params'] = dict()
            report_params['fails'] = list()

            for subtasks in report:
                crops_params = subtasks["crops_params"]

                # Probably there's only one subtask
                # but we can iterate over whole list.
                for subtask_num, crop in crops_params.items():

                    report_params['crops_params'][subtask_num] = crop

                    # Copy fail if it existed.
                    if subtasks.get('fail_reason') is not None:
                        report_params['fails'][subtask_num].append(
                            subtasks['fail_reason'])

            return report_params
        return report

    def to_file(self, directory: str, part: int):
        os.makedirs(directory, exist_ok=True)

        all_path = os.path.join(directory, 'all_tests{}.json'.format(part))
        with open(all_path, 'w') as outfile:
            json.dump(self.all_params, outfile, indent=4, sort_keys=False)

        failed_path = os.path.join(directory,
                                   'failed_tests{}.json'.format(part))
        with open(failed_path, 'w') as outfile:
            json.dump(self.failed_params, outfile, indent=4, sort_keys=False)

        success_path = os.path.join(directory,
                                    'success_tests{}.json'.format(part))
        with open(success_path, 'w') as outfile:
            json.dump(self.success_params, outfile, indent=4, sort_keys=False)

    def clear_reports(self):
        self.failed_params: List[dict] = list()
        self.success_params: List[dict] = list()
        self.all_params: List[dict] = list()


class ExtendedVerifierTestEnv:

    def __init__(self):
        self.report = Report()

    def run(self):

        ExtendedVerifierTest.setUpClass()

        try:
            parameters_sets = self._generate_parameters()
            self.run_for_params(parameters_sets)
        except (Exception, RuntimeError) as e:
            print("Script error ocured: {}".format(repr(e)))
        finally:
            ExtendedVerifierTest.tearDownClass()

    def _run_parameters_set(self, parameters):
        try:
            tester = ExtendedVerifierTest()

            tester.setUp()
            tester.run_for_parameters_set(parameters)

        except (Exception, RuntimeError) as e:
            _, _, tb = sys.exc_info()
            message = traceback.format_exc()
            tb_info = traceback.extract_tb(tb)
            filename, line, function, _ = tb_info[-1]

            reason = {
                'exception': repr(e),
                'line': line,
                'filename': filename,
                'function': function,
                'stacktrace': message,
                'tmp_dir': tester.tempdir
            }

            self.report.fail(parameters, reason)
        else:
            report = tester.report
            report.merge_reports_content()

            self.report.update(report)
        finally:
            tester.tearDown()

    def run_for_params(self, parameters_sets: List[dict]):
        logger.info("Parameters {}".format(str(parameters_sets)))

        num_sets = len(parameters_sets)
        print("Running {} parameters sets.".format(num_sets))

        counter = 0
        max_sets_in_batch = 100
        part = 0

        for parameters_set in parameters_sets:
            try:
                self._run_parameters_set(parameters_set)
            except (Exception, RuntimeError) as e:
                print("Saving to file partial results.")
                self._reports_to_files(part)
                raise e

            self._progress()

            # Reports consume to much space to keep them in memory
            # all the time.
            counter += 1
            if counter >= max_sets_in_batch:
                counter = 0
                self._reports_to_files(part)
                self.report.clear_reports()
                part += 1

        # Add newline on end.
        print("")
        self._print_fails()
        self._reports_to_files(part)

    def _print_fails(self):
        print("Printing failed tests:")
        print(json.dumps(self.report.failed_params, indent=4, sort_keys=False))

    def _progress(self):
        # Print dot for each test to indicate progress like in pytest.
        print(".", end='')
        sys.stdout.flush()

    def _reports_to_files(self, part):
        self.report.to_file("reports", part)

    def _generate_parameters(self):
        # resolutions_list = [[400, 400]]
        # subtasks_num_list = range(1, 4)
        # num_frames = [list(range(1, 2))]
        resolutions_list = [[400, 400]]
        subtasks_num_list = list(range(1, 40))
        num_frames = self._generate_num_frames(1, 2)

        return self._generate_combinations(resolutions_list, subtasks_num_list,
                                           num_frames)

    def _generate_num_frames(self, min_num_frames: int, max_num_frames: int):
        return [
            list(range(1, i + 1))
            for i in range(min_num_frames, max_num_frames + 1)
        ]

    @classmethod
    def _generate_combinations(cls, resolutions_list: List[List[int]],
                               subtasks_num_list: List[int],
                               frames_list: List[List[int]]):
        parameters_set = []

        for resolution in resolutions_list:
            for subtasks_num in subtasks_num_list:
                for frames in frames_list:
                    params = ExtendedVerifierTest._build_params(
                        resolution, subtasks_num, frames, {})
                    parameters_set.append(params)
        return parameters_set


# pylint: disable=too-many-ancestors
class ExtendedVerifierTest(TestBlenderIntegration):

    def __init__(self):
        super().__init__()
        self.report: Report = Report()

    def run_for_parameters_set(self, parameters_set: dict):

        resolution = parameters_set['resolution']
        subtasks = parameters_set['subtasks_count']
        frames = parameters_set['frames']

        # TODO: Use these parameters to test chosen crops.
        # crops_params = parameters_set['crops_params']

        task_def = self._task_dictionary(
            scene_file=self._get_chessboard_scene(),
            resolution=resolution,
            subtasks_count=subtasks,
            frames=frames)

        task: Task = self.start_task(task_def)

        for i in range(task.task_definition.subtasks_count):
            result, subtask_id, _ = self.compute_next_subtask(task, i)

            try:
                result = self.verify_subtask(task, subtask_id, result)
                self._assert_crops_match(task.task_definition.task_id)

                if not result:
                    raise RuntimeError("Verification (decision tree) resulted "
                                       "in negative response.")

            except (Exception, RuntimeError):
                parameters_set_copy = self._add_crop_params(
                    parameters_set, task, i)

                reason = {
                    'exception': "Crops don't match.",
                    'tmp_dir': self.tempdir
                }

                self.report.fail(parameters_set_copy, reason)
            else:
                self.report.success(
                    self._add_crop_params(parameters_set, task, i))

        result = task.task_definition.output_file
        for file in result:
            if not os.path.isfile(file):
                raise RuntimeError("Result file [{}] doesn't exist.".format(
                    file))

    def _add_crop_params(self, parameters_set: dict, task: Task,
                         subtask_num: int):
        parameters_set_copy = copy.deepcopy(parameters_set)
        crops = self._deduce_crop_parameters(task.task_definition.task_id)

        parameters_set_copy['crops_params'] = dict()
        parameters_set_copy['crops_params'][subtask_num] = crops['crops']

        return parameters_set_copy

    def _assert_crops_match(self, task_id: str) -> None:
        task_dir = os.path.join(self.tempdir, task_id)

        try:
            crops_paths = find_crop_files_in_path(
                os.path.join(task_dir, 'output'))
            fragments_paths = find_fragments_in_path(
                os.path.join(task_dir, "work"))
        except Exception:
            raise Exception(
                "Can't find crop files in output or work directory.")

        assert crops_paths, "There were no crops produced!"
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

    def _deduce_crop_parameters(self, task_id: str) -> dict:
        task_dir = os.path.join(self.tempdir, task_id)
        params_file = os.path.join(task_dir, 'work',
                                   'blender_render_params.json')

        with open(params_file, "r") as file:
            return json.load(file)

    @classmethod
    def _build_params(cls, resolution: List[int], subtasks: int,
                      frames: List[int], crops_params: dict):
        return {
            'resolution': resolution,
            'subtasks_count': subtasks,
            'frames': frames,
            'crops_params': crops_params
        }


def run_script():
    test_env = ExtendedVerifierTestEnv()
    test_env.run()


if __name__ == "__main__":
    run_script()
