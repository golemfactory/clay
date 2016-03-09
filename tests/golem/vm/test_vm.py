from unittest import TestCase

from golem.vm.vm import PythonVM, PythonProcVM


class TestPythonVM(TestCase):
    def test_good_task(self):
        vm = PythonVM()
        self.assertIsInstance(vm, PythonVM)
        self.assertEqual(vm.scope, {})
        code = "cnt=0\nfor i in range(n):\n\tcnt += i\noutput=cnt"
        extra_arg = {'n': 10000}
        result, err = vm.run_task(code, extra_arg)
        self.assertIsNone(err)
        self.assertEqual(result, (extra_arg["n"] - 1) * extra_arg["n"] * 0.5)

        vm = PythonProcVM()
        self.assertIsInstance(vm, PythonProcVM)
        self.assertEqual(vm.scope, {})
        extra_arg = {'n': 10000}
        result, err = vm.run_task(code, extra_arg)

        self.assertIsNone(err)
        self.assertEqual(result, (extra_arg["n"] - 1) * extra_arg["n"] * 0.5)

    def test_exception_task(self):
        vm = PythonVM()
        code = "raise Exception('some error')"
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertEqual(err, "some error")

        vm = PythonProcVM()
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertEqual(err, "some error")

    def test_no_output(self):
        vm = PythonVM()
        code = "print 'hello'"
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertIsNone(err)

        vm = PythonProcVM()
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertIsNone(err)
