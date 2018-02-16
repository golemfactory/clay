from golem_messages.message import ComputeTaskDef
import os
import unittest.mock as mock
from os import path

import array
import unittest
from random import randrange, shuffle

import OpenEXR
from PIL import Image

from apps.blender.task.blenderrendertask import (BlenderDefaults,
                                                 BlenderRenderTask,
                                                 BlenderRenderTaskBuilder,
                                                 BlenderRendererOptions,
                                                 generate_expected_offsets,
                                                 BlenderTaskTypeInfo,
                                                 PreviewUpdater,
                                                 logger)
from apps.rendering.resources.imgrepr import load_img
from apps.rendering.task.renderingtask import PREVIEW_Y, PREVIEW_X
from apps.rendering.task.renderingtaskstate import (
    RenderingTaskDefinition)
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import ResultType
from golem.task.taskstate import SubtaskStatus, SubtaskState
from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from apps.core.task.coretask import logger as logger_core
from golem.verification.verifier import SubtaskVerificationState



class TestBlenderDefaults(unittest.TestCase):


    def test_init(self):
        bd = BlenderDefaults()
        self.assertTrue(path.isfile(bd.main_program_file))


class BlenderTaskInitTest(TempDirFixture, LogTestCase):
    def test_compositing(self):

        task_definition = RenderingTaskDefinition()
        task_definition.options = BlenderRendererOptions()
        task_definition.options.use_frames = True
        task_definition.options.frames = [7, 8, 10]
        task_definition.main_scene_file = self.temp_file_name("example.blend")
        task_definition.output_file = self.temp_file_name('output')
        task_definition.output_format = 'PNG'
        task_definition.resolution = [2, 300]
        task_definition.task_id = "ABC"

        def _get_blender_task(task_definition, total_tasks=6):
            return BlenderRenderTask(
                node_name="exmaple-node-name",
                task_definition=task_definition,
                total_tasks=total_tasks,
                root_path=self.tempdir,
            )

        # Compostiting set to False
        task_definition.options.compositing = False
        bt = _get_blender_task(task_definition)
        assert not bt.compositing

        # Compositing True, use frames, more subtasks than frames
        task_definition.options.compositing = True
        with self.assertLogs(logger, level="WARNING") as logs:
            bt = _get_blender_task(task_definition)
        assert not bt.compositing
        assert any("ABC" in log for log in logs.output)
        assert any("Compositing not supported" for log in logs.output)

        # Compositing True, use frames, as many subtasks as frames
        bt = _get_blender_task(task_definition, 3)
        assert bt.compositing

        # Compositing True, use frames, less subtasks than frames
        bt = _get_blender_task(task_definition, 1)
        assert bt.compositing

        # Compositing True, use frames is False, as many subtask as frames
        task_definition.options.use_frames = False
        with self.assertLogs(logger, level="WARNING") as logs:
            bt = _get_blender_task(task_definition, 3)
        assert not bt.compositing
        assert any("ABC" in log for log in logs.output)
        assert any("Compositing not supported" for log in logs.output)


class TestBlenderFrameTask(TempDirFixture):
    def setUp(self):
        super(TestBlenderFrameTask, self).setUp()
        task_definition = RenderingTaskDefinition()
        task_definition.options = BlenderRendererOptions()
        task_definition.options.compositing = False
        task_definition.options.use_frames = True
        task_definition.options.frames = [7, 8, 10]
        task_definition.main_scene_file = self.temp_file_name("example.blend")
        task_definition.output_file = self.temp_file_name('output')
        task_definition.output_format = 'PNG'
        task_definition.resolution = [200, 300]
        self.bt = BlenderRenderTask(
            node_name="example-node-name",
            task_definition=task_definition,
            total_tasks=6,
            root_path=self.tempdir,
        )

        dm = DirManager(self.path)
        self.bt.initialize(dm)

    def test_init_preview(self):
        self.assertEqual(len(self.bt.preview_file_path),
                         len(self.bt.frames))
        self.assertEqual(len(self.bt.preview_task_file_path),
                         len(self.bt.frames))

    def test_computation_failed_or_finished(self):
        assert self.bt.total_tasks == 6

        # Failed compuation stays failed
        extra_data1 = self.bt.query_extra_data(1000, 2, "ABC", "abc")
        assert extra_data1.ctd is not None
        extra_data2 = self.bt.query_extra_data(1000, 2, "DEF", "def")
        assert extra_data2.ctd is not None

        self.bt.computation_failed(extra_data1.ctd['subtask_id'])
        self.bt.computation_finished(extra_data1.ctd['subtask_id'], [],
                                     ResultType.DATA)
        assert self.bt.subtasks_given[extra_data1.ctd['subtask_id']][
                   'status'] == \
               SubtaskStatus.failure

        # Successful computation
        extra_data3 = self.bt.query_extra_data(1000, 2, "FGH", "fgh")
        assert extra_data3.ctd is not None
        file_dir = path.join(self.bt.tmp_dir, extra_data3.ctd['subtask_id'])
        if not path.exists(file_dir):
            os.makedirs(file_dir)

        file1 = path.join(file_dir, 'result1')
        img = Image.new("RGB", (self.bt.res_x, self.bt.res_y // 2))
        img.save(file1, "PNG")

        def verification_finished1(*args, **kwargs):
            # extra_data3.ctd['results'] = kwargs['results']

            result = {'reference_data': None,
                      'message': "",
                      'time_started': None,
                      'time_ended': None,
                      'extra_data': {}}
            result['extra_data']['results'] = kwargs['results']
            self.bt.verification_finished(
                extra_data3.ctd['subtask_id'],
                SubtaskVerificationState.VERIFIED,
                result)

        with mock.patch(
                'apps.core.task.verifier.CoreVerifier.start_verification',
                side_effect=verification_finished1):
            self.bt.computation_finished(extra_data3.ctd['subtask_id'], [file1],
                                         ResultType.FILES, lambda: None)
            assert self.bt.subtasks_given[extra_data3.ctd['subtask_id']][
                       'status'] == SubtaskStatus.finished

        def verification_finished2(*args, **kwargs):
            result = {'reference_data': None,
                      'message': "",
                      'time_started': None,
                      'time_ended': None,
                      'extra_data': {}}
            result['extra_data']['results'] = kwargs['results']
            self.bt.verification_finished(
                extra_data4.ctd['subtask_id'],
                SubtaskVerificationState.VERIFIED,
                result)

        extra_data4 = self.bt.query_extra_data(1000, 2, "FFF", "fff")
        assert extra_data4.ctd is not None

        file2 = path.join(file_dir, 'result2')
        img.save(file2, "PNG")
        img.close()

        with mock.patch(
                'apps.core.task.verifier.CoreVerifier.start_verification',
                side_effect=verification_finished2):
            self.bt.computation_finished(extra_data4.ctd['subtask_id'], [file2],
                                         ResultType.FILES, lambda: None)
            assert self.bt.subtasks_given[extra_data4.ctd['subtask_id']][
                       'status'] == SubtaskStatus.finished

        str_ = self.temp_file_name(self.bt.outfilebasename) + '0008.PNG'
        assert path.isfile(str_)

        assert len(self.bt.preview_file_path) == len(self.bt.frames)
        assert len(self.bt.preview_task_file_path) == len(self.bt.frames)

    def test_query_extra_data(self):

        # If num frames == num subtask, make sure that
        # blender script describe whole frame
        self.bt.total_tasks = 3
        extra_data = self.bt.query_extra_data(100, node_id="node1",
                                              node_name="node11",
                                              num_cores=0)
        assert not extra_data.should_wait
        assert extra_data.ctd is not None
        assert "border_max_y = 1" in extra_data.ctd['extra_data']['script_src']
        assert "border_min_y = 0" in extra_data.ctd['extra_data']['script_src']

    def test_put_frame_together(self):
        self.bt.output_format = "EXR"
        self.bt.output_file += ".EXR"
        chunks = 12
        res_y = 0
        for i in range(1, chunks + 1):  # Subtask numbers start from 1.
            y = randrange(1, 100)
            res_y += y
            file1 = self.temp_file_name('chunk{}.exr'.format(i))
            exr = OpenEXR.OutputFile(file1, OpenEXR.Header(self.bt.res_x, y))
            data = array.array('f', [1.0] * (self.bt.res_x * y)).tostring()
            exr.writePixels({'R': data, 'G': data, 'B': data,
                             'F': data, 'A': data})
            exr.close()
            self.bt.frames_given["7"][i-1] = file1
        self.bt._put_frame_together(7, 2)


class TestBlenderTask(TempDirFixture, LogTestCase):
    def build_bt(self, res_x, res_y, total_tasks, frames=None):
        output_file = self.temp_file_name('output')
        if frames is None:
            use_frames = False
            frames = [1]
        else:
            use_frames = True

        task_definition = RenderingTaskDefinition()
        task_definition.options = BlenderRendererOptions()
        task_definition.options.use_frames = use_frames
        task_definition.options.frames = frames
        task_definition.output_file = output_file
        task_definition.output_format = "PNG"
        task_definition.resolution = [res_x, res_y]
        task_definition.main_scene_file = path.join(self.path, "example.blend")
        bt = BlenderRenderTask(node_name="example-node-name",
                               task_definition=task_definition,
                               total_tasks=total_tasks,
                               root_path=self.tempdir,
                               )
        bt.initialize(DirManager(self.tempdir))
        return bt

    def setUp(self):
        super(TestBlenderTask, self).setUp()
        self.bt = self.build_bt(2, 300, 7)
        dm = DirManager(self.path)
        self.bt.initialize(dm)

    def test_after_test(self):
        self.assertEqual(self.bt.after_test({}, None), {})
        self.assertEqual(self.bt.after_test({"notData": []}, None), {})

        outlog = self.temp_file_name("out.log")
        errlog = self.temp_file_name("err.log")
        notalog = self.temp_file_name("notalog.png")

        fd_out = open(outlog, 'w')
        fd_out.close()

        fd_err = open(errlog, 'w')
        fd_err.close()

        results = {"data": {notalog, outlog, errlog}}
        after_test_data = self.bt.after_test(results, None)

        self.assertEqual(after_test_data, {})

        with open(outlog, 'w') as fd_out:
            fd_out.write("Warning: path 'example/directory/to/file/f1.png' "
                         "not found\nwarning: Path "
                         "'example/directory/to/file2.png' not fouND\n"
                         "warning: Path 'example/directory/to/file2.png' "
                         "not fouND")

        with open(errlog, 'w') as fd_err:
            fd_err.write("Warning: path "
                         "'example/directory/to/another/file3.png' "
                         "not found\nexample/to/file4.png")

        results = {"data": {notalog, outlog, errlog}}
        after_test_data = self.bt.after_test(results, None)
        warnings = after_test_data["warnings"]

        self.assertTrue("f1.png" in warnings)
        self.assertTrue("file2.png" in warnings)
        self.assertTrue("file3.png" in warnings)
        self.assertEqual(warnings.count("file2.png"), 1)
        self.assertFalse("file4.png" in warnings)

        with open(outlog, 'w') as fd_out:
            fd_out.write("Error: engine COMPLETELY UNKNOWN ENGINE not found")

        with open(errlog, 'w') as fd_err:
            fd_err.write("Error: But not important at all")

        after_test_data = self.bt.after_test(results, None)
        warnings = after_test_data["warnings"]
        self.assertTrue("COMPLETELY UNKNOWN ENGINE" in warnings)

    def test_query_extra_data_for_test_task(self):
        self.bt.use_frames = True

        self.bt.frames = [1, 2, 3, 5, 7, 11, 13]
        ctd = self.bt.query_extra_data_for_test_task()
        self.assertIsInstance(ctd, ComputeTaskDef)
        self.assertTrue(ctd['extra_data']['frames'] == [1])

        self.bt.frames = [2]
        ctd = self.bt.query_extra_data_for_test_task()
        self.assertIsInstance(ctd, ComputeTaskDef)
        self.assertTrue(ctd['extra_data']['frames'] == [1])

        self.bt.use_frames = False
        self.bt.frames = [1]
        ctd = self.bt.query_extra_data_for_test_task()
        self.assertIsInstance(ctd, ComputeTaskDef)
        self.assertTrue(ctd['extra_data']['frames'] == [1])

    def test_blender_task(self):
        self.assertIsInstance(self.bt, BlenderRenderTask)
        self.assertEqual(self.bt.main_scene_file,
                         path.join(self.path, "example.blend"))
        extra_data = self.bt.query_extra_data(1000, 2, "ABC", "abc")
        ctd = extra_data.ctd
        assert ctd['extra_data']['start_task'] == 1
        assert ctd['extra_data']['end_task'] == 1
        self.bt.last_task = self.bt.total_tasks
        self.bt.subtasks_given[1] = {'status': SubtaskStatus.finished}
        assert self.bt.query_extra_data(1000, 2, "ABC", "abc").ctd is None

    def test_get_min_max_y(self):
        self.assertEqual(self.bt.res_x, 2)
        self.assertEqual(self.bt.res_y, 300)
        self.assertEqual(self.bt.total_tasks, 7)
        for tasks in [1, 6, 7, 20, 60]:
            self.bt.total_tasks = tasks
            for yres in range(1, 100):
                self.bt.res_y = yres
                cur_max_y = self.bt.res_y
                for i in range(1, self.bt.total_tasks + 1):
                    min_y, max_y = self.bt._get_min_max_y(i)
                    min_y = int(float(self.bt.res_y) * min_y)
                    max_y = int(float(self.bt.res_y) * max_y)
                    self.assertTrue(max_y == cur_max_y)
                    cur_max_y = min_y
                self.assertTrue(cur_max_y == 0)

        self.bt.use_frames = True
        self.bt.frames = [4, 5, 10, 11, 12]
        self.bt.total_tasks = 20
        self.bt.res_y = 300
        assert self.bt._get_min_max_y(2) == (0.5, 0.75)

    def test_put_img_together_exr(self):
        for chunks in [1, 5, 7, 11, 13, 31, 57, 100]:
            res_y = 0
            self.bt.collected_file_names = {}
            for i in range(1, chunks + 1):  # Subtask numbers start from 1.
                y = randrange(1, 100)
                res_y += y
                file1 = self.temp_file_name('chunk{}.exr'.format(i))
                exr = OpenEXR.OutputFile(file1,
                                         OpenEXR.Header(self.bt.res_x, y))
                data = array.array('f', [1.0] * (self.bt.res_x * y)).tostring()
                exr.writePixels({'R': data, 'G': data, 'B': data,
                                 'F': data, 'A': data})
                exr.close()
                self.bt.collected_file_names[i] = file1
            self.bt.res_y = res_y
            self.bt._put_image_together()
            self.assertTrue(path.isfile(self.bt.output_file))
            img = Image.open(self.bt.output_file)
            img_x, img_y = img.size
            img.close()
            self.assertTrue(self.bt.res_x == img_x and res_y == img_y)

        self.bt.restart()
        assert self.bt.preview_updater.chunks == {}
        assert self.bt.preview_updater.perfectly_placed_subtasks == 0
        assert self.bt.preview_updater.perfect_match_area_y == 0

    def test_put_img_together_exr_to_exr(self):
        self.bt.output_format = "EXR"
        self.bt.output_file += ".EXR"
        for chunks in [1, 5, 7, 11, 13, 31, 57]:
            res_y = 0
            self.bt.collected_file_names = {}
            for i in range(1, chunks + 1):  # Subtask numbers start from 1.
                y = randrange(1, 100)
                res_y += y
                file1 = self.temp_file_name('chunk{}.exr'.format(i))
                exr = OpenEXR.OutputFile(file1,
                                         OpenEXR.Header(self.bt.res_x, y))
                data = array.array('f', [1.0] * (self.bt.res_x * y)).tostring()
                exr.writePixels({'R': data, 'G': data, 'B': data,
                                 'F': data, 'A': data})
                exr.close()
                self.bt.collected_file_names[i] = file1
            self.bt.res_y = res_y
            self.bt._put_image_together()
            self.assertTrue(path.isfile(self.bt.output_file))
            img = load_img(self.bt.output_file)
            img_x, img_y = img.get_size()
            self.assertEqual(self.bt.res_x, img_x)
            self.assertEqual(self.bt.res_y, img_y)

    def test_put_img_together_not_exr(self):
        for output_format in ["PNG", "JPEG", "BMP"]:
            self.bt.output_format = output_format.lower()
            for chunks in [1, 5, 7, 11, 13, 31, 57, 100]:
                res_y = 0
                self.bt.collected_file_names = {}
                for i in range(1, chunks + 1):  # subtask numbers start from 1
                    y = randrange(1, 100)
                    res_y += y
                    file1 = self.temp_file_name(
                        'chunk{}.{}'.format(i, output_format.lower())
                    )
                    img = Image.new("RGB", (self.bt.res_x, y))
                    img.save(file1, output_format.upper())
                    self.bt.collected_file_names[i] = file1
                self.bt.res_y = res_y
                self.bt._put_image_together()
                self.assertTrue(path.isfile(self.bt.output_file))
                img = Image.open(self.bt.output_file)
                img_x, img_y = img.size
                self.assertTrue(self.bt.res_x == img_x and res_y == img_y)

    def test_update_frame_preview(self):
        file1 = self.temp_file_name('preview1.exr')
        file2 = self.temp_file_name('preview2.exr')
        file3 = self.temp_file_name('preview3.bmp')
        file4 = self.temp_file_name('preview4.bmp')

        bt = self.build_bt(300, 200, 2, frames=[1, 2, 3, 4])
        bt.preview_updaters = [PreviewUpdater(f, bt.res_x, bt.res_y,
                                              {1: 0, 2: 99})
                               for f in [file1, file2, file3, file4]]

        img1 = OpenEXR.OutputFile(file1, OpenEXR.Header(bt.res_x, 99))
        data = array.array('f', [1.0] * (bt.res_x * 99)).tostring()
        img1.writePixels({'R': data, 'G': data, 'B': data,
                          'F': data, 'A': data})
        img1.close()

        img2 = OpenEXR.OutputFile(file2, OpenEXR.Header(bt.res_x, 101))
        data = array.array('f', [1.0] * (bt.res_x * 101)).tostring()
        img2.writePixels({'R': data, 'G': data, 'B': data,
                          'F': data, 'A': data})
        img2.close()

        bt._update_frame_preview(file1, 1, part=1)
        assert bt.preview_updaters[0].perfect_match_area_y == 99
        self.assertTrue(bt.preview_updaters[0].perfectly_placed_subtasks == 1)

        bt._update_frame_preview(file2, 1, part=2)
        self.assertTrue(bt.preview_updaters[0].perfect_match_area_y == 200)
        self.assertTrue(bt.preview_updaters[0].perfectly_placed_subtasks == 2)

        bt.preview_file_path = []
        bt.preview_file_path.append(file3)
        bt.preview_task_file_path = []
        bt.preview_task_file_path.append(file4)

        img1 = OpenEXR.OutputFile(file1, OpenEXR.Header(bt.res_x, 99))
        data = array.array('f', [1.0] * (bt.res_x * 99)).tostring()
        img1.writePixels({'R': data, 'G': data, 'B': data,
                          'F': data, 'A': data})
        img1.close()

        bt._update_frame_preview(file1, 1, part=1, final=True)
        img = Image.open(file3)
        self.assertTrue(img.size == (300, 200))
        img = Image.open(file4)
        self.assertTrue(img.size == (300, 200))

        preview = BlenderTaskTypeInfo.get_preview(bt, single=False)
        assert isinstance(preview, dict)
        assert len(preview) == 4
        assert all(p is None or os.path.exists(p) for p in preview.values())

        preview = BlenderTaskTypeInfo.get_preview(bt, single=True)
        assert isinstance(preview, str)
        assert os.path.exists(preview)

        preview = BlenderTaskTypeInfo.get_preview(None, single=True)
        assert preview is None

        bt.restart()
        for preview in bt.preview_updaters:
            assert preview.chunks == {}
            assert preview.perfect_match_area_y == 0
            assert preview.perfectly_placed_subtasks == 0

    def test_mark_task_area(self):
        bt = self.build_bt(300, 200, 2, frames=[1, 2])

        file1 = self.temp_file_name('preview1.bmp')
        img_task = Image.new("RGB", (bt.res_x, bt.res_y))
        img_task.save(file1, "BMP")
        color = (0, 0, 255)

        # test the case in which a single subtask is a whole frame

        self.assertEqual(bt.frames, [1, 2])
        bt._mark_task_area(None, img_task, color, 0)
        for i in range(0, bt.res_x):
            for j in range(0, bt.res_y):
                pixel = img_task.getpixel((i, j))
                self.assertTrue(pixel == color)

        # test the case with frames divided into multiple subtasks

        bt = self.build_bt(600, 200, 4, frames=[2, 3])
        subtask = {"start_task": 2, "end_task": 2}
        file2 = self.temp_file_name('preview2.bmp')
        img_task2 = Image.new("RGB", (bt.res_x, bt.res_y))
        img_task2.save(file2, "BMP")
        bt._mark_task_area(subtask, img_task2, color)
        pixel = img_task2.getpixel((0, 99))
        self.assertTrue(pixel == (0, 0, 0))
        pixel = img_task2.getpixel((0, 100))
        self.assertTrue(pixel == color)

    def test_query_extra_data(self):
        extra_data = self.bt.query_extra_data(100000, num_cores=0,
                                              node_id='node',
                                              node_name='node')
        assert extra_data.ctd
        subtask_id = extra_data.ctd['subtask_id']
        assert not extra_data.should_wait

        extra_data = self.bt.query_extra_data(100000, num_cores=0,
                                              node_id='node',
                                              node_name='node')
        assert extra_data.should_wait

        # Write log with warning and don't return data or should wait
        # if client was banned
        self.bt.computation_failed(subtask_id)
        with self.assertLogs(logger_core, level="WARNING"):
            extra_data = self.bt.query_extra_data(100000, num_cores=0,
                                                  node_id='node',
                                                  node_name='node')
        assert extra_data.ctd is None
        assert not extra_data.should_wait


    def test_update_preview(self):
        bt = self.build_bt(300, 200, 10)
        dm = DirManager(self.tempdir)
        bt.initialize(dm)
        files = self.additional_dir_content([1])
        preview = files[0]
        img = Image.new("RGBA", (20, 200))
        img.save(preview, "PNG")
        bt._update_preview(preview, 3)

        preview = BlenderTaskTypeInfo.get_preview(bt, single=False)
        assert isinstance(preview, dict)
        assert len(preview) == 1
        assert all(os.path.exists(p) for p in preview.values())

        preview = BlenderTaskTypeInfo.get_preview(bt, single=True)
        assert os.path.exists(preview)

        preview = BlenderTaskTypeInfo.get_preview(None, single=True)
        assert preview is None


class TestPreviewUpdater(TempDirFixture, LogTestCase):
    def test_update_preview(self):
        preview_file = self.temp_file_name('sample_img.png')
        res_x = 200

        for chunks in range(1, 13):
            res_y = 0
            expected_offsets = {}
            chunks_sizes = {}
            for i in range(1, chunks + 1):  # Subtask numbers start from 1.
                y = randrange(1, 100)
                expected_offsets[i] = res_y
                chunks_sizes[i] = y
                res_y += y

            if res_x != 0 and res_y != 0:
                if float(res_x) / float(res_y) > float(PREVIEW_X) / PREVIEW_Y:
                    scale_factor = float(PREVIEW_X) / res_x
                else:
                    scale_factor = float(PREVIEW_Y) / res_y
                scale_factor = min(1.0, scale_factor)
            else:
                scale_factor = 1.0

            pu = PreviewUpdater(preview_file, res_x, res_y, expected_offsets)
            chunks_list = list(range(1, chunks + 1))
            shuffle(chunks_list)
            for i in chunks_list:
                img = Image.new("RGB", (res_x, chunks_sizes[i]))
                file1 = self.temp_file_name('chunk{}.png'.format(i))
                img.save(file1)
                pu.update_preview(file1, i)
            if int(round(res_y * scale_factor)) != PREVIEW_Y:
                self.assertAlmostEqual(pu.perfect_match_area_y,
                                       res_y * scale_factor)
            self.assertTrue(pu.perfectly_placed_subtasks == chunks)

    def test_error_in_preview_update(self):
        pu = PreviewUpdater(None, PREVIEW_X, PREVIEW_Y, {})
        with self.assertLogs(logger, level="WARNING"):
            pu.update_preview("Not existing", 4)


class TestBlenderRenderTaskBuilder(TempDirFixture):
    def test_build(self):
        definition = RenderingTaskDefinition()
        definition.total_subtasks = 1
        definition.options = BlenderRendererOptions()
        builder = BlenderRenderTaskBuilder(node_name="ABC",
                                           task_definition=definition,
                                           root_path=self.tempdir,
                                           dir_manager=DirManager(self.tempdir))
        blender_task = builder.build()
        self.assertIsInstance(blender_task, BlenderRenderTask)


class TestHelpers(unittest.TestCase):
    @staticmethod
    def _get_task_border(as_path=False):
        offsets = generate_expected_offsets(30, 800, 600)
        subtask = SubtaskState()

        definition = RenderingTaskDefinition()
        definition.options = BlenderRendererOptions()
        definition.options.use_frames = False
        definition.resolution = [800, 600]

        for k in range(1, 31):
            subtask.extra_data = {'start_task': k, 'end_task': k}
            border = BlenderTaskTypeInfo.get_task_border(subtask, definition,
                                                         30, as_path=as_path)
            assert min(border) == (0, offsets[k])
            assert max(border) == (797, offsets[k + 1] - 1)

        definition.options.use_frames = True
        definition.options.frames = list(range(2))
        offsets = generate_expected_offsets(15, 800, 600)

        for k in range(1, 31):
            subtask.extra_data = {'start_task': k, 'end_task': k}
            border = BlenderTaskTypeInfo.get_task_border(subtask, definition,
                                                         30, as_path=as_path)
            i = (k - 1) % 15 + 1
            assert min(border) == (0, offsets[i])
            assert max(border) == (798, offsets[i + 1] - 1)

        subtask.extra_data = {'start_task': 2, 'end_task': 2}
        definition.options.use_frames = True
        definition.options.frames = list(range(30))
        if as_path:
            assert BlenderTaskTypeInfo.get_task_border(subtask, definition,
                                                       30, as_path=as_path) == \
                   [(0, 600), (800, 600), (800, 0), (0, 0)]
        else:
            assert BlenderTaskTypeInfo.get_task_border(subtask, definition,
                                                       30, as_path=as_path) == \
                   []

        definition.options.use_frames = False
        definition.resolution = (0, 0)
        assert BlenderTaskTypeInfo.get_task_border(subtask, definition,
                                                   30, as_path=as_path) == []

    def test_get_task_border(self):
        self._get_task_border()

    def test_get_task_border_path(self):
        self._get_task_border(as_path=True)

    def test_get_task_num_from_pixels(self):
        offsets = generate_expected_offsets(30, 1920, 1080)
        frame_offsets = generate_expected_offsets(15, 1920, 1080)
        task_definition = RenderingTaskDefinition()
        task_definition.options = BlenderRendererOptions()
        task_definition.resolution = [1920, 1080]

        for k in range(1, 31):
            task_definition.options.use_frames = False
            num = BlenderTaskTypeInfo.get_task_num_from_pixels(
                6, offsets[k] + 1, task_definition, 30
            )
            assert num == k

            task_definition.options.use_frames = True
            task_definition.options.frames = list(range(30))
            num = BlenderTaskTypeInfo.get_task_num_from_pixels(
                1, 0, task_definition, 30, k
            )
            assert num == k

            i = (k - 1) % 15 + 1
            task_definition.options.frames = list(range(2))
            num = BlenderTaskTypeInfo.get_task_num_from_pixels(
                1, frame_offsets[i] + 3, task_definition, 30, (k - 1) // 15 + 1
            )
            assert num == k

        task_definition.options.use_frames = False
        assert BlenderTaskTypeInfo.get_task_num_from_pixels(
            5, 1200, task_definition, 30
        ) == 30
