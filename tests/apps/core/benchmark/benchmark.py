from PIL import Image

from apps.core.benchmark.benchmark import Benchmark
from gnr.renderingtaskstate import RenderingTaskDefinition
from golem.testutils import TempDirFixture


class TestBlenderBenchmark(TempDirFixture):
    benchmark = Benchmark()
    
    def verify_log_helper(self, file_content):
        file_ = self.temp_file_name("log.log")
        fd = open(file_, "w")
        fd.write(file_content)
        fd.close()
        return self.benchmark.verify_log(file_)
    
    def test_is_instance(self):
        self.assertIsInstance(self.benchmark, Benchmark)
        self.assertIsInstance(self.benchmark.task_definition, RenderingTaskDefinition)
    
    def test_query_benchmark_task_definition(self):
        td = self.benchmark.query_benchmark_task_definition()
        self.assertIsInstance(td, RenderingTaskDefinition)
        self.assertTrue(td.max_price == 100)
        self.assertTrue(td.resolution == [200, 100])
        self.assertTrue(td.full_task_timeout == 10000)
        self.assertTrue(td.subtask_timeout == 10000)
        self.assertFalse(td.optimize_total)
        self.assertTrue(td.resources == set())
        self.assertTrue(td.total_tasks == 1)
        self.assertTrue(td.total_subtasks == 1)
        self.assertTrue(td.start_task == 1)
        self.assertTrue(td.end_task == 1)
        
    def test_verify_img(self):
        img = Image.new("RGB", (200, 100))
        file_ = self.temp_file_name("img.png")
        fd = open(file_, "w")
        img.save(fd, "PNG")
        self.assertTrue(self.benchmark.verify_img(file_))
        img = Image.new("RGB", (201, 100))
        img.save(fd, "PNG")
        self.assertFalse(self.benchmark.verify_img(file_))
    
    def test_verify_log(self):
        for fc in ["Error", "ERROR", "error", "blaErRor", "bla ERRor bla"]:
            self.assertFalse(self.verify_log_helper(fc))
        for fc in ["123", "erro r", "asd sda", "sad 12 sad;"]:
            self.assertTrue(self.verify_log_helper(fc))
