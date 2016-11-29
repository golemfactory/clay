import os

from gnr.renderingdirmanager import find_task_script
from golem.testutils import TempDirFixture


class TestRenderingDirManager(TempDirFixture):

    def test_find_task_script(self):
        script_path = os.path.join(self.path, "resources", "scripts")
        os.makedirs(script_path)
        script = os.path.join(script_path, "bla")
        open(script, "w").close()
        task_file = os.path.join(self.path, "task", "testtask.py")
        path = find_task_script(task_file, "bla")
        self.assertTrue(os.path.isdir(os.path.dirname(path)))
        self.assertEqual(os.path.basename(path), "bla")
