import os.path
import subprocess
import tempfile
import unittest


class TestTempFiles(unittest.TestCase):

    def test_running_script_from_temp_file(self):
        """Creates a temporary file, writes a python code into it and runs it"""
        test_dir = "testdata"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=test_dir, delete=False) as tmp_file:
            name = tmp_file.name
            self.assertTrue(os.path.exists(name))
            tmp_file.write("print 'hello!'")
            tmp_file.flush()
            cmd = ['python', name]
            proc = subprocess.Popen(cmd, stdout = subprocess.PIPE)
            proc.wait()
            out = proc.stdout.read()
            self.assertEquals(out.rstrip(), 'hello!')

        if os.path.exists(tmp_file.name):
            os.remove(tmp_file.name)
        self.assertFalse(os.path.exists(tmp_file.name))