import json
import uuid

from apps.core.benchmark.benchmarkrunner import CoreBenchmark
from apps.glambda.task.glambdatask import (
    GLambdaTask,
    GLambdaTaskDefinition,
)


class GLambdaTaskBenchmark(CoreBenchmark):
    EXPECTED_OUTPUT = 'test arg'
    EXPECTED_FILE_OUTPUT = json.dumps({"data": "test arg"})

    def __init__(self):
        self._normalization_constant = 1000
        self._task_definition = GLambdaTaskDefinition()
        self._task_definition.name = 'GLambda'
        self._task_definition.task_id = str(uuid.uuid4())
        self._task_definition.subtasks_count = 1
        self._task_definition.resources = []
        self._task_definition.compute_on = 'cpu'

        serializer = GLambdaTask.PythonObjectSerializer()

        my_args = ' arg'

        def test_task(args):
            return 'test' + args

        self._task_definition.options.method = serializer.serialize(test_task)
        self._task_definition.options.args = serializer.serialize(my_args)
        self._task_definition.options.verification = {
            'type': GLambdaTask.VerificationMethod.NO_VERIFICATION
        }
        self._task_definition.options.outputs = ['result.json', 'stdout.log',
                                                 'stderr.log']

    @property
    def normalization_constant(self):
        return self._normalization_constant

    @property
    def task_definition(self):
        return self._task_definition

    def verify_result(self, result_data_path) -> bool:
        result_json_file = None
        for f in result_data_path:
            if f.endswith('result.json'):
                result_json_file = f

        if not result_json_file:
            return False

        with open(result_json_file, 'r') as f:
            try:
                json_obj = json.loads(f.read())
            except json.decoder.JSONDecodeError:
                return False
            if 'data' not in json_obj:
                return False
            return json_obj['data'] == self.EXPECTED_OUTPUT
