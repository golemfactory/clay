import shutil
import os
import tempfile
from unittest import mock, TestCase

import pytest

from apps.blender.firejailenvironment.task_thread import \
    BlenderFirejailTaskThread
from apps.rendering.task.rendering_engine_requirement import RenderingEngine
from golem.core.common import get_golem_path
from golem import testutils


class TestFirejailTaskThread(TestCase, testutils.PEP8MixIn):
    PEP8_FILES = (
        "apps/blender/firejailenvironment/task_thread.py",
    )

    @pytest.mark.firejail
    def test_blender_task(self):
        try:
            test_dir = tempfile.TemporaryDirectory(
                prefix='firejail_test_',
                dir='/tmp'
            ).name
            script_path = os.path.join(test_dir, 'script')
            res_path = os.path.join(get_golem_path(),
                                    'apps/blender/benchmark/test_task/')
            tmp_path = os.path.join(test_dir, 'tmp')
            work_path = os.path.join(test_dir, 'work')
            out_path = os.path.join(test_dir, 'output')
            os.makedirs(script_path)
            os.makedirs(tmp_path)
            os.makedirs(work_path)
            os.makedirs(out_path)
            extra_data = {
                'frames': [*range(1, 10)],
                'scene_file': 'cube.blend',
                'outfilebasename': 'out_basename',
                'start_task': 1,
                'output_format': 'PNG',
                'script_src': ''
            }

            task_thread = BlenderFirejailTaskThread(
                task_computer=mock.MagicMock(),
                subtask_id='subtask',
                script_dir=script_path,
                src_code='',
                extra_data=extra_data,
                short_desc='short description',
                res_path=res_path,
                tmp_path=tmp_path,
                timeout=10.0,
                rendering_engine=RenderingEngine.CPU,
                memory_limit=1024*1024,
                cpu_num_cores_limit=2,
                check_mem=True
            )
            task_thread.run()

            result, est_mem = task_thread.result
            self.assertTrue(est_mem)
            self.assertTrue(result['data'])
            for f in result['data']:
                self.assertTrue(os.path.isfile(f))
            self.assertFalse(task_thread.error)
            self.assertTrue(task_thread.done)
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
