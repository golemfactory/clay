import unittest
import os

from gnr.task.blenderrendertask import BlenderDefaults, BlenderRenderTask


class TestBlenderDefaults(unittest.TestCase):
    def test_init(self):
        bd = BlenderDefaults()
        self.assertTrue(os.path.isfile(bd.main_program_file))

class TestBlenderTaskDivision(unittest.TestCase):
    program_file = "example_program_file"
    open(program_file, 'w').close()
    bt = BlenderRenderTask(
                 node_name = "example-node-name",
                 task_id = "example-task-id",
                 main_scene_dir = os.getcwd(),
                 main_scene_file = "example.blend",
                 main_program_file = program_file,
                 total_tasks = 7,
                 res_x = 200,
                 res_y = 300,
                 outfilebasename = "example_out",
                 output_file = "",
                 output_format = "PNG",
                 full_task_timeout = 1,
                 subtask_timeout = 1,
                 task_resources = [],
                 estimated_memory = 123,
                 root_path = os.getcwd(),
                 use_frames = False,
                 frames = [1],
                 engine = "CYCLES"
                 )
    
    def test_blender_task(self):
        self.assertIsInstance(self.bt, BlenderRenderTask)
        self.assertTrue(self.bt.main_scene_file == "example.blend")

    def test_get_min_max_y(self):
        self.assertTrue(self.bt.res_x == 200)
        self.assertTrue(self.bt.res_y == 300)
        self.assertTrue(self.bt.total_tasks == 7)
        for tasks in [1, 6, 7, 20, 60]:
            self.bt.total_tasks = tasks
            for yres in range(100, 1000):
                self.bt.res_y = yres
                cur_max_y = self.bt.res_y
                for i in range(1, self.bt.total_tasks + 1):
                    min_y, max_y = self.bt._get_min_max_y(i)
                    min_y = int(float(self.bt.res_y) * (min_y))
                    max_y = int(float(self.bt.res_y) * (max_y)) 
                    self.assertTrue(max_y == cur_max_y)
                    cur_max_y = min_y
                self.assertTrue(cur_max_y == 0)
        
