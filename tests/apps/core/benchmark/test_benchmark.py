import mock
from PIL import Image

from apps.core.benchmark import benchmark
from golem.testutils import TempDirFixture


class TestBenchmark(TempDirFixture):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.benchmark = benchmark.Benchmark()

    def test_verify_img(self):
        filepath = self.temp_file_name("img.png")
        fd = open(filepath, "w")

        resolution = self.benchmark.task_definition.resolution

        img = Image.new("RGB", resolution)
        img.save(fd, "PNG")
        self.assertTrue(self.benchmark.verify_img(filepath))

        img = Image.new("RGB", (resolution[0]+1, resolution[1]))
        img.save(fd, "PNG")
        self.assertFalse(self.benchmark.verify_img(filepath))

    def test_broken_image(self):
        filepath = self.temp_file_name("broken.png")
        with open(filepath, "w") as f:
            f.write('notanimage,notanimageatall')
        with mock.patch('apps.core.benchmark.benchmark.logger') as m:
            self.assertFalse(self.benchmark.verify_img(filepath))
            m.warning.assert_called_once_with(mock.ANY, exc_info=True)

    def test_verify_log(self):
        def verify_log(file_content):
            filepath = self.temp_file_name("log.log")
            fd = open(filepath, "w")
            fd.write(file_content)
            fd.close()
            return self.benchmark.verify_log(filepath)
        for fc in ["Error", "ERROR", "error", "blaErRor", "bla ERRor bla"]:
            self.assertFalse(verify_log(fc))
        for fc in ["123", "erro r", "asd sda", "sad 12 sad;"]:
            self.assertTrue(verify_log(fc))

    def test_verify_result(self):
        """Wether verify_result calls correct methods."""

        with mock.patch.multiple(self.benchmark, verify_img=mock.DEFAULT, verify_log=mock.DEFAULT) as mocks:
            self.assertTrue(self.benchmark.verify_result(['a.txt', 'b.gif']))
            self.assertEqual(mocks['verify_img'].call_count, 0)
            self.assertEqual(mocks['verify_log'].call_count, 0)

            for m in mocks.values():
                m.return_value = True
            paths = [
                '/mnt/dummy/image.png',
                '../important.log',
            ]
            self.assertTrue(self.benchmark.verify_result(paths))
            mocks['verify_img'].assert_called_once_with(paths[0])
            mocks['verify_log'].assert_called_once_with(paths[1])

            for m in mocks.values():
                m.reset_mock()
                m.return_value = False

            self.assertFalse(self.benchmark.verify_result([paths[0]]))
            self.assertFalse(self.benchmark.verify_result([paths[1]]))
            mocks['verify_img'].assert_called_once_with(paths[0])
            mocks['verify_log'].assert_called_once_with(paths[1])

    def test_find_resources(self):
        """Simplistic test of basic implementation."""
        self.assertEquals(self.benchmark.find_resources(), set())
