
from TaskBase import Task, TaskHeader

from taskablerenderer import TaskableRenderer, RenderTaskResult, RenderTaskDesc
from Resource import prepare_delta_zip
from simplehash import SimpleHash

from takscollector import PbrtTaksCollector
import os
import cPickle as pickle

import random

from img import Img

test_taskScr2 = """
from minilight import render_task
from resource import ArrayResource
from base64 import encodestring

res = render_task("d:/src/golem/poc/golemPy/testtasks/minilight/cornellbox.ml.txt", start_x, start_y, width, height, img_width, img_height)

output = encodestring(res)
"""


class RayTracingTask(Task):
    #######################
    def __init__(self, width, height, task_header, return_address = "", return_port = 0):
        coderes = test_taskScr2
        Task.__init__(self, task_header, [], coderes, 0)
        self.width = width
        self.height = height
        self.split_index = 0
        self.return_address = return_address
        self.return_port = return_port

    #######################
    def query_extra_data(self, perf_index):
        hash_ = "{}".format(random.getrandbits(128))
        return {    "start_x" : 0,
                    "start_y" : 0,
                    "width" : self.width,
                    "height" : self.height,
                    "img_width" : self.width,
                    "img_height" : self.height }, hash_, self.return_address, self.return_port

    #######################
    def short_extra_data_repr(self, perf_index):
        return self.query_extra_data(perf_index).__str__()

    #######################
    def needs_computation(self):
        if self.split_index < 1:
            return True
        else:
            return False

    #######################
    def computation_started(self, extra_data):
        self.split_index += 1

    #######################
    def computation_finished(self, subtask_id, task_result, env = None):
        print "Receive computed task id:{} \n result:{}".format(self.task_header.task_id, task_result)

TIMESLC  = 45.0
TIMEOUT  = 100000.0

task_data = u'''
(0.278 0.275 -0.789) (0 0 1) 40


(0.0906 0.0943 0.1151) (0.1 0.09 0.07)


(0.556 0.000 0.000) (0.006 0.000 0.559) (0.556 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.006 0.000 0.559) (0.556 0.000 0.000) (0.003 0.000 0.000)  (0.7 0.7 0.7) (0 0 0)

(0.556 0.000 0.559) (0.000 0.549 0.559) (0.556 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.559) (0.556 0.000 0.559) (0.006 0.000 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.006 0.000 0.559) (0.000 0.549 0.000) (0.000 0.549 0.559)  (0.7 0.2 0.2) (0 0 0)
(0.000 0.549 0.000) (0.006 0.000 0.559) (0.003 0.000 0.000)  (0.7 0.2 0.2) (0 0 0)

(0.556 0.000 0.000) (0.556 0.549 0.559) (0.556 0.549 0.000)  (0.2 0.7 0.2) (0 0 0)
(0.556 0.549 0.559) (0.556 0.000 0.000) (0.556 0.000 0.559)  (0.2 0.7 0.2) (0 0 0)

(0.556 0.549 0.559) (0.000 0.549 0.000) (0.556 0.549 0.000)  (0.7 0.7 0.7) (0 0 0)
(0.000 0.549 0.000) (0.556 0.549 0.559) (0.000 0.549 0.559)  (0.7 0.7 0.7) (0 0 0)

(0.343 0.545 0.332) (0.213 0.545 0.227) (0.343 0.545 0.227)  (0.7 0.7 0.7) (1000 1000 1000)
(0.213 0.545 0.227) (0.343 0.545 0.332) (0.213 0.545 0.332)  (0.7 0.7 0.7) (1000 1000 1000)


(0.474 0.165 0.225) (0.426 0.165 0.065) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.316 0.165 0.272) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)

(0.266 0.000 0.114) (0.266 0.165 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)
(0.316 0.000 0.272) (0.266 0.000 0.114) (0.316 0.165 0.272)  (0.7 0.7 0.7) (0 0 0)

(0.316 0.000 0.272) (0.316 0.165 0.272) (0.474 0.165 0.225)  (0.7 0.7 0.7) (0 0 0)
(0.474 0.165 0.225) (0.316 0.000 0.272) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.474 0.000 0.225) (0.474 0.165 0.225) (0.426 0.165 0.065)  (0.7 0.7 0.7) (0 0 0)
(0.426 0.165 0.065) (0.426 0.000 0.065) (0.474 0.000 0.225)  (0.7 0.7 0.7) (0 0 0)

(0.426 0.000 0.065) (0.426 0.165 0.065) (0.266 0.165 0.114)  (0.7 0.7 0.7) (0 0 0)
(0.266 0.165 0.114) (0.266 0.000 0.114) (0.426 0.000 0.065)  (0.7 0.7 0.7) (0 0 0)


(0.133 0.330 0.247) (0.291 0.330 0.296) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.084 0.330 0.406) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.133 0.000 0.247) (0.133 0.330 0.247) (0.084 0.330 0.406)  (0.7 0.7 0.7) (0 0 0)
(0.084 0.330 0.406) (0.084 0.000 0.406) (0.133 0.000 0.247)  (0.7 0.7 0.7) (0 0 0)

(0.084 0.000 0.406) (0.084 0.330 0.406) (0.242 0.330 0.456)  (0.7 0.7 0.7) (0 0 0)
(0.242 0.330 0.456) (0.242 0.000 0.456) (0.084 0.000 0.406)  (0.7 0.7 0.7) (0 0 0)

(0.242 0.000 0.456) (0.242 0.330 0.456) (0.291 0.330 0.296)  (0.7 0.7 0.7) (0 0 0)
(0.291 0.330 0.296) (0.291 0.000 0.296) (0.242 0.000 0.456)  (0.7 0.7 0.7) (0 0 0)

(0.291 0.000 0.296) (0.291 0.330 0.296) (0.133 0.330 0.247)  (0.7 0.7 0.7) (0 0 0)
(0.133 0.330 0.247) (0.133 0.000 0.247) (0.291 0.000 0.296)  (0.7 0.7 0.7) (0 0 0)'''

class VRayTracingTask(Task):
    #######################
    def __init__(self, width, height, num_samples, header, file_name, return_address = "", return_port = 0):

        src_file = open("../testtasks/minilight/compact_src/renderer.py", "r")
        src_code = src_file.read()

        Task.__init__(self, header, src_code)

        self.header.ttl = max(width * height * num_samples * 2 / 2200.0, TIMEOUT)

        self.taskable_renderer = None

        self.w = width
        self.h = height
        self.num_samples = num_samples

        self.last_extra_data = ""
        self.file_name = file_name
        self.return_address = return_address
        self.return_port = return_port

    #######################
    def __init_renderer(self):
        self.taskable_renderer = TaskableRenderer(self.w, self.h, self.num_samples, None, TIMESLC, TIMEOUT)

    def initialize(self):
        self.__init_renderer()

    #######################
    def query_extra_data(self, perf_index):

        task_desc = self.taskable_renderer.getNextTaskDesc(perf_index)

        self.last_extra_data =  {    "id" : task_desc.getID(),
                    "x" : task_desc.getX(),
                    "y" : task_desc.getY(),
                    "w" : task_desc.getW(),
                    "h" : task_desc.getH(),
                    "num_pixels" : task_desc.getNumPixels(),
                    "num_samples" : task_desc.getNumSamples(),
                    "task_data" : task_data
                    }

        hash_ = "{}".format(random.getrandbits(128))
        return self.last_extra_data, hash_, self.return_address, self.return_port

    #######################
    def short_extra_data_repr(self, perf_index):
        if self.last_extra_data:
            l = self.last_extra_data
            return "x: {}, y: {}, w: {}, h: {}, num_pixels: {}, num_samples: {}".format(l["x"], l["y"], l["w"], l["h"], l["num_pixels"], l["num_samples"])

        return ""

    #######################
    def needs_computation(self):
        return self.taskable_renderer.hasMoreTasks()

    #######################
    def computation_started(self, extra_data):
        pass

    #######################
    def computation_finished(self, subtask_id, task_result, env = None):
        #dest = RenderTaskDesc(0, extra_data[ "x" ], extra_data[ "y" ], extra_data[ "w" ], extra_data[ "h" ], extra_data[ "num_pixels" ] ,extra_data[ "num_samples" ])
        #res = RenderTaskResult(dest, task_result)
        #self.taskable_renderer.task_finished(res)
        #if self.taskable_renderer.isFinished():
        #    VRayTracingTask.__save_image(self.file_name + ".ppm", self.w, self.h, self.taskable_renderer.getResult(), self.num_samples) #FIXME: change file name here
        pass

    #######################
    def get_total_tasks(self):
        return self.taskable_renderer.total_tasks

    #######################
    def get_total_chunks(self):
        return self.taskable_renderer.pixelsCalculated

    #######################
    def get_active_tasks(self):
        return self.taskable_renderer.active_tasks

    #######################
    def get_active_chunks(self):
        return self.taskable_renderer.nextPixel - self.taskable_renderer.pixelsCalculated

    #######################
    def get_chunks_left(self):
        return self.taskable_renderer.pixelsLeft

    #######################
    def get_progress(self):
        return self.taskable_renderer.get_progress()

    #######################
    @classmethod
    def __save_image(cls, img_name, w, h, data, num_samples):
        if not data:
            print "No data to write"
            return False

        img = Img(w, h)
        img.copyPixels(data)

        image_file = open(img_name, 'wb')
        img.get_formatted(image_file, num_samples)
        image_file.close()


from golem.core.compress import decompress

class PbrtRenderTask(Task):

    #######################
    def __init__(self, header, path_root, total_tasks, num_subtasks, num_cores, outfilebasename, scene_file, return_address = "", return_port = 0):

        src_file = open("../testtasks/pbrt/pbrt_compact.py", "r")
        src_code = src_file.read()

        Task.__init__(self, header, src_code)

        self.header.ttl = max(2200.0, TIMEOUT)

        self.path_root           = path_root
        self.last_task           = 0
        self.total_tasks         = total_tasks
        self.num_subtasks        = num_subtasks
        self.num_cores           = num_cores
        self.outfilebasename    = outfilebasename
        self.scene_file          = scene_file

        self.last_extra_data      = None

        self.collector          = PbrtTaksCollector()
        self.num_tasks_received   = 0
        self.return_address      = return_address
        self.return_port         = return_port
        self.subtasks_given      = {}

    def initialize(self):
        pass

    #######################
    def query_extra_data(self, perf_index):

        end_task = min(self.last_task + 1, self.total_tasks)

        self.last_extra_data =  {     "path_root" : self.path_root,
                                    "start_task" : self.last_task,
                                    "end_task" : end_task,
                                    "total_tasks" : self.total_tasks,
                                    "num_subtasks" : self.num_subtasks,
                                    "num_cores" : self.num_cores,
                                    "outfilebasename" : self.outfilebasename,
                                    "scene_file" : self.scene_file
                                }

        hash_ = "{}".format(random.getrandbits(128))
        self.subtasks_given[ hash_ ] = self.last_extra_data
        self.last_task = end_task # TODO: Should depend on performance
        return self.last_extra_data, hash_, self.return_address, self.return_port

    #######################
    def __short_extra_data_repr(self, perf_index, extra_data):
        l = extra_data
        return "path_root: {}, start_task: {}, end_task: {}, total_tasks: {}, num_subtasks: {}, num_cores: {}, outfilebasename: {}, scene_file: {}".format(l["path_root"], l["start_task"], l["end_task"], l["total_tasks"], l["num_subtasks"], l["num_cores"], l["outfilebasename"], l["scene_file"])


    #######################
    def needs_computation(self):
        return self.last_task != self.total_tasks

    #######################
    def computation_started(self, extra_data):
        pass

    #######################
    def computation_finished(self, subtask_id, task_result, env = None):

        tmp_dir = env.get_task_temporary_dir(self.header.task_id)

        if len(task_result) > 0:
            for trp in task_result:
                tr = pickle.loads(trp)
                fh = open(os.path.join(tmp_dir, tr[ 0 ]), "wb")
                fh.write(decompress(tr[ 1 ]))
                fh.close()
        
                self.collector.add_img_file(os.path.join(tmp_dir, tr[ 0 ])) # pewnie tutaj trzeba czytac nie zpliku tylko z streama
                self.num_tasks_received += 1
                

        if self.num_tasks_received == self.total_tasks:
            self.collector.finalize().save("{}.png".format(os.path.join(env.get_task_output_dir(self.header.task_id), "test")), "PNG")

    #######################
    def get_total_tasks(self):
        return self.total_tasks

    #######################
    def get_total_chunks(self):
        return self.total_tasks

    #######################
    def get_active_tasks(self):
        return self.last_task

    #######################
    def get_active_chunks(self):
        return self.last_task

    #######################
    def get_chunks_left(self):
        return self.total_tasks - self.last_task

    #######################
    def get_progress(self):
        return float(self.last_task) / self.total_tasks

    #######################
    def prepare_resource_delta(self, subtask_id, task_id, resource_header):
        if subtask_id in self.subtasks_given:
            dir_name = os.path.join("res", self.header.client_id, self.header.task_id, "resources")
            tmp_dir = os.path.join("res", self.header.client_id, self.header.task_id, "tmp")

            if os.path.exists(dir_name):
                return prepare_delta_zip(dir_name, resource_header, tmp_dir)
            else:
                return None
        else:
            return None