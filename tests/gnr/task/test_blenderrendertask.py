import array
import unittest
from os import path
from random import randrange, shuffle

import OpenEXR
from PIL import Image

from golem.task.taskstate import SubtaskStatus
from golem.testutils import TempDirFixture

from gnr.task.blenderrendertask import (BlenderDefaults, BlenderRenderTaskBuilder, BlenderRenderTask,
                                        BlenderRendererOptions, PreviewUpdater)
from gnr.renderingtaskstate import RenderingTaskDefinition


class TestBlenderDefaults(unittest.TestCase):
    def test_init(self):
        bd = BlenderDefaults()
        self.assertTrue(path.isfile(bd.main_program_file))


class TestBlenderFrameTask(TempDirFixture):
    def test_init_preview(self):
        program_file = self.temp_file_name('program')
        output_file = self.temp_file_name('output')
        bt = BlenderRenderTask(node_name="example-node-name",
                               task_id="example-task-id",
                               main_scene_dir=self.tempdir,
                               main_scene_file="example.blend",
                               main_program_file=program_file,
                               total_tasks=7,
                               res_x=2,
                               res_y=300,
                               outfilebasename="example_out",
                               output_file=output_file,
                               output_format="PNG",
                               full_task_timeout=1,
                               subtask_timeout=1,
                               task_resources=[],
                               estimated_memory=123,
                               root_path=self.tempdir,
                               use_frames=True,
                               frames=[10],
                               compositing=False,
                               max_price=10)

        assert len(bt.preview_file_path) == len(bt.frames)
        assert len(bt.preview_task_file_path) == len(bt.frames)


class TestBlenderTask(TempDirFixture):
    def build_bt(self, res_x, res_y, total_tasks, frames=[]):
        program_file = self.temp_file_name('program')
        output_file = self.temp_file_name('output')
        if frames == []:
            use_frames = False
            frames = [1]
        else:
            use_frames = True
        bt = BlenderRenderTask(node_name="example-node-name",
                                    task_id="example-task-id",
                                    main_scene_dir=self.tempdir,
                                    main_scene_file=path.join(self.path, "example.blend"),
                                    main_program_file=program_file,
                                    total_tasks=total_tasks,
                                    res_x=res_x,
                                    res_y=res_y,
                                    outfilebasename="example_out",
                                    output_file=output_file,
                                    output_format="PNG",
                                    full_task_timeout=1,
                                    subtask_timeout=1,
                                    task_resources=[],
                                    estimated_memory=123,
                                    root_path=self.tempdir,
                                    use_frames=use_frames,
                                    compositing=False,
                                    frames=frames,
                                    max_price=10)
        return bt
    
    def setUp(self):
        super(TestBlenderTask, self).setUp()
        program_file = self.temp_file_name('program')
        output_file = self.temp_file_name('output')
        self.bt = self.build_bt(2, 300, 7)
        
    def test_blender_task(self):
        self.assertIsInstance(self.bt, BlenderRenderTask)
        self.assertTrue(self.bt.main_scene_file == path.join(self.path, "example.blend"))
        extra_data = self.bt.query_extra_data(1000, 2, "ABC", "abc")
        ctd = extra_data.ctd
        assert ctd.extra_data['start_task'] == 1
        assert ctd.extra_data['end_task'] == 1
        self.bt.last_task = self.bt.total_tasks
        self.bt.subtasks_given[1] = {'status': SubtaskStatus.finished}
        assert self.bt.query_extra_data(1000, 2, "ABC", "abc").ctd is None

    def test_get_min_max_y(self):
        self.assertTrue(self.bt.res_x == 2)
        self.assertTrue(self.bt.res_y == 300)
        self.assertTrue(self.bt.total_tasks == 7)
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

    def test_put_img_together_exr(self):
        for chunks in [1, 5, 7, 11, 13, 31, 57, 100]:
            res_y = 0
            self.bt.collected_file_names = {}
            for i in range(1, chunks + 1):  # Subtask numbers start from 1.
                y = randrange(1, 100)
                res_y += y
                file1 = self.temp_file_name('chunk{}.exr'.format(i))
                exr = OpenEXR.OutputFile(file1, OpenEXR.Header(self.bt.res_x, y))
                data = array.array('f', [1.0] * (self.bt.res_x * y)).tostring()
                exr.writePixels({'R': data, 'G': data, 'B': data, 'F': data, 'A': data})
                exr.close()
                self.bt.collected_file_names[i] = file1
            self.bt.res_y = res_y
            self.bt._put_image_together(self.tempdir)
            self.assertTrue(path.isfile(self.bt.output_file))
            img = Image.open(self.bt.output_file)
            img_x, img_y = img.size
            self.assertTrue(self.bt.res_x == img_x and res_y == img_y)

    def test_put_img_together_not_exr(self):
        for output_format in ["PNG", "JPEG", "BMP"]:
            self.bt.output_format = output_format.lower()
            for chunks in [1, 5, 7, 11, 13, 31, 57, 100]:
                res_y = 0
                self.bt.collected_file_names = {}
                for i in range(1, chunks + 1):  # subtask numbers start from 1
                    y = randrange(1, 100)
                    res_y += y
                    file1 = self.temp_file_name('chunk{}.{}'.format(i, output_format.lower()))
                    img = Image.new("RGB", (self.bt.res_x, y))
                    img.save(file1, output_format.upper())
                    self.bt.collected_file_names[i] = file1
                self.bt.res_y = res_y
                self.bt._put_image_together(self.tempdir)
                self.assertTrue(path.isfile(self.bt.output_file))
                img = Image.open(self.bt.output_file)
                img_x, img_y = img.size
                self.assertTrue(self.bt.res_x == img_x and res_y == img_y)
                
    def test_update_frame_preview(self):
        file1 = self.temp_file_name('preview1.exr')
        file2 = self.temp_file_name('preview2.exr')
        file3 = self.temp_file_name('preview3.bmp')
        file4 = self.temp_file_name('preview4.bmp')
        
        bt = self.build_bt(300, 200, 2, frames=[1])
        bt.preview_updaters = [PreviewUpdater(file1, bt.res_x, bt.res_y, {1: 0, 2: 99})]
        
        img1 = OpenEXR.OutputFile(file1, OpenEXR.Header(bt.res_x, 99))
        data = array.array('f', [1.0] * (bt.res_x * 99)).tostring()
        img1.writePixels({'R': data, 'G': data, 'B': data, 'F': data, 'A': data})
        img1.close()
        
        img2 = OpenEXR.OutputFile(file2, OpenEXR.Header(bt.res_x, 101))
        data = array.array('f', [1.0] * (bt.res_x * 101)).tostring()
        img2.writePixels({'R': data, 'G': data, 'B': data, 'F': data, 'A': data})
        img2.close()        
        
        bt._update_frame_preview(file1, 1, part=1)
        self.assertTrue(bt.preview_updaters[0].perfect_match_area_y == 99)
        self.assertTrue(bt.preview_updaters[0].perfectly_placed_subtasks == 1)
        
        bt._update_frame_preview(file2, 1, part=2)
        self.assertTrue(bt.preview_updaters[0].perfect_match_area_y == 200)
        self.assertTrue(bt.preview_updaters[0].perfectly_placed_subtasks == 2)
        
        bt.preview_file_path = []
        bt.preview_file_path.append(file3)
        bt.preview_task_file_path = []
        bt.preview_task_file_path.append(file4)
        
        bt._update_frame_preview(file1, 1, part=1, final=True)
        img = Image.open(file3)
        self.assertTrue(img.size == (300, 99))
        img = Image.open(file4)
        self.assertTrue(img.size == (300, 99))
        

    def test_mark_task_area(self):
        bt = self.build_bt(300, 200, 2, frames=[1, 2])
        
        file1 = self.temp_file_name('preview1.bmp')
        img_task = Image.new("RGB", (bt.res_x, bt.res_y))
        img_task.save(file1, "BMP")
        color = (0, 0, 255)
        
        # test the case in which a single subtask is a whole frame
        
        self.assertTrue(bt.frames == [1, 2])
        bt._mark_task_area(None, img_task, color, 0)
        for i in range(0, bt.res_x):
            for j in range(0, bt.res_y):
                pixel = img_task.getpixel((i, j))
                self.assertTrue(pixel == color)
        

        # test the case with frames divided into multiple subtasks
        
        file2 = self.temp_file_name('preview2.bmp')
        img_task2 = Image.new("RGB", (bt.res_x, bt.res_y))
        img_task2.save(file2, "BMP")
        
        file3 = self.temp_file_name('preview3.bmp')
        img_task3 = Image.new("RGB", (bt.res_x, bt.res_y))
        img_task3.save(file3, "BMP")
        
        bt = self.build_bt(600, 200, 6, frames=[2, 3])
        bt.frames = [2, 3]
        bt.total_tasks = 6
        expected_offsets = {1: 0, 2: 66, 3: 133}
        bt.preview_updaters = [PreviewUpdater(file2, bt.res_x, bt.res_y, expected_offsets),
                               PreviewUpdater(file3, bt.res_x, bt.res_y, expected_offsets)
                              ]                
        bt.preview_updaters[0].perfect_match_area_y = 34
        bt.preview_updaters[0].perfectly_placed_subtasks = 1
        subtask = {"start_task": 2}
        bt._mark_task_area(subtask, img_task2, color, 0)
        for i in range(0, 300):
            pixel = img_task2.getpixel((i, 33))
            self.assertTrue(pixel == (0, 0, 0))
            pixel = img_task2.getpixel((i, 133))
            self.assertTrue(pixel == (0, 0, 0))
            for j in range(34, 67):
                pixel = img_task2.getpixel((i, j))
                self.assertTrue(pixel == color)

    def test_query_extra_data(self):
        extra_data = self.bt.query_extra_data(100000, num_cores=0, node_id='node', node_name='node')
        assert extra_data.ctd
        assert not extra_data.should_wait

        extra_data = self.bt.query_extra_data(100000, num_cores=0, node_id='node', node_name='node')
        assert extra_data.should_wait


class TestPreviewUpdater(TempDirFixture):
    def test_update_preview(self):
        preview_file = self.temp_file_name('sample_img.png')
        res_x = 200

        for chunks in range(1, 100):
            res_y = 0
            expected_offsets = {}
            chunks_sizes = {}
            for i in range(1, chunks + 1):  # Subtask numbers start from 1.
                y = randrange(1, 100)
                expected_offsets[i] = res_y
                chunks_sizes[i] = y
                res_y += y
            
            if res_x != 0 and res_y != 0:
                if float(res_x) / float(res_y) > 300. / 200.:
                    scale_factor = 300. / res_x
                else:
                    scale_factor = 200. / res_y
                scale_factor = min(1.0, scale_factor)
            else:
                scale_factor = 1.0
            
            pu = PreviewUpdater(preview_file, res_x, res_y, expected_offsets)
            chunks_list = range(1, chunks + 1)
            shuffle(chunks_list)
            for i in chunks_list:
                img = Image.new("RGB", (res_x, chunks_sizes[i]))
                file1 = self.temp_file_name('chunk{}.png'.format(i))
                img.save(file1)
                pu.update_preview(file1, i)
            print pu.perfect_match_area_y, res_y * scale_factor
            if int(round(res_y * scale_factor)) != 200:
                self.assertAlmostEqual(pu.perfect_match_area_y, res_y * scale_factor)
            self.assertTrue(pu.perfectly_placed_subtasks == chunks)


class TestBlenderRenderTaskBuilder(TempDirFixture):
    def test_build(self):
        definition = RenderingTaskDefinition()
        definition.renderer_options = BlenderRendererOptions()
        builder = BlenderRenderTaskBuilder(node_name="ABC", task_definition=definition, root_path=self.tempdir)
        blender_task = builder.build()
        self.assertIsInstance(blender_task, BlenderRenderTask)
