from copy import copy
from unittest import TestCase

from golem.vm.vm import PythonVM, PythonProcVM, PythonTestVM, exec_code


class TestPythonVM(TestCase):
    def test_good_task(self):
        vm = PythonVM()
        self.assertIsInstance(vm, PythonVM)
        self.assertEqual(vm.scope, {})
        code = "cnt=0\nfor i in range(n):\n\tcnt += i\noutput=cnt"
        extra_arg = {'n': 10000}
        cnt = (extra_arg["n"] - 1) * extra_arg["n"] * 0.5
        result, err = vm.run_task(code, copy(extra_arg))
        self.assertIsNone(err)
        self.assertEqual(result, cnt)

        vm = PythonProcVM()
        self.assertIsInstance(vm, PythonProcVM)
        self.assertEqual(vm.scope, {})
        result, err = vm.run_task(code, copy(extra_arg))
        self.assertIsNone(err)
        self.assertEqual(result, cnt)

        vm = PythonTestVM()
        self.assertIsInstance(vm, PythonTestVM)
        extra_arg = {'n': 10000}
        result, err = vm.run_task(code, copy(extra_arg))
        self.assertIsNone(err)
        res, mem = result
        self.assertEqual(res, cnt)
        self.assertGreaterEqual(mem, 0)

        scope = copy(extra_arg)
        exec_code(code, scope)
        self.assertEqual(scope["output"], cnt)
        self.assertIsNone(scope.get("error"))

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

        vm = PythonTestVM()
        (result, mem), err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertGreaterEqual(mem, 0)
        self.assertEqual(err, "some error")

        scope = {}
        exec_code(code, scope)
        self.assertIsNone(scope.get("output"))
        self.assertEqual(scope["error"], "some error")

    def test_no_output(self):
        vm = PythonVM()
        code = "print 'hello hello'"
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertIsNone(err)

        vm = PythonProcVM()
        result, err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertIsNone(err)

        vm = PythonTestVM()
        (result, mem), err = vm.run_task(code, {})
        self.assertIsNone(result)
        self.assertGreaterEqual(mem, 0)
        self.assertIsNone(err)

        scope = {}
        # with self.assertRaises(KeyError):
        #     exec_code(code, scope)
        exec_code(code, scope)
        self.assertIsNone(scope.get("error"))
