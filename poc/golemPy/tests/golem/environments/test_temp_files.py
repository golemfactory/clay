import subprocess
import tempfile
import unittest


class TestTempFiles(unittest.TestCase):

    def test_named_temp_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir=".") as tmp_file:
            tmp_file.write("print 'hello!'")
            tmp_file.flush()
            cmd = ['/usr/bin/python', tmp_file.name]
            proc = subprocess.Popen(cmd, stdout = subprocess.PIPE)
            proc.wait()
            out = proc.stdout.read()
            self.assertEquals(out.rstrip(), 'hello!')

