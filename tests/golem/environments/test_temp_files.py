import os.path
import subprocess
import tempfile

from golem.tools.testdirfixture import TestDirFixture


class TestTempFiles(TestDirFixture):

    def test_running_script_from_temp_file(self):
        """Creates a temporary file, writes a python code into it and runs it"""
        test_dir = os.path.join(self.path, "testdata")
        test_dir_created = False
        if not os.path.isdir(test_dir):
            test_dir_created = True
            os.mkdir(test_dir)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=test_dir, delete=False) as tmp_file:
            name = tmp_file.name
            self.assertTrue(os.path.exists(name))
            tmp_file.write("print 'hello!'")
        cmd = ['python', name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        proc.wait()
        out = proc.stdout.read()
        self.assertEquals(out.rstrip(), 'hello!')

        self.assertTrue(os.path.exists(tmp_file.name))
        self.assertTrue(os.path.join(test_dir, os.path.basename(tmp_file.name)))
        os.remove(tmp_file.name)
        self.assertFalse(os.path.exists(tmp_file.name))
        if test_dir_created:
            os.removedirs(test_dir)
