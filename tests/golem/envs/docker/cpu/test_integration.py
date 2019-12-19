import socket

import pytest
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from golem.envs import RuntimeStatus
from golem.envs.docker import DockerPrerequisites, DockerRuntimePayload
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.envs.docker.whitelist import Whitelist
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip


@ci_skip
@pytest.mark.slow
class TestIntegration(TestCase, DatabaseFixture):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        # pylint: disable=protected-access
        hypervisor_cls = DockerCPUEnvironment._get_hypervisor_class()
        assert hypervisor_cls is not None, "No supported hypervisor found"

        cls.hypervisor = hypervisor_cls(get_config_fn=lambda: {})
        cls.vm_was_running = cls.hypervisor.vm_running

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.vm_was_running:
            cls.hypervisor.restore_vm()
        super().tearDownClass()

    @inlineCallbacks
    def setUp(self):
        DatabaseFixture.setUp(self)
        # Not using simply self.new_path as work_dir because this path changes
        # with every test case. On Windows the working directory has to be
        # shared so using self.new_path would result with a pop-up window
        # appearing during every test.
        config = DockerCPUConfig(work_dirs=[self.new_path.parent.parent])
        self.env = DockerCPUEnvironment(config)
        yield self.env.prepare()

        # Download busybox image
        Whitelist.add("busybox")
        installed = yield self.env.install_prerequisites(DockerPrerequisites(
            image="busybox",
            tag="latest"
        ))
        self.assertTrue(installed)

    @inlineCallbacks
    def tearDown(self):
        yield self.env.clean_up()
        DatabaseFixture.tearDown(self)

    @pytest.mark.timeout(120)  # 120 sec should be well enough for this test
    @inlineCallbacks
    def test_io(self):
        # Create runtime
        runtime = self.env.runtime(DockerRuntimePayload(
            image="busybox",
            tag="latest",
            env={},
            command="sh -c 'cat -'"
        ))

        # Prepare container
        yield runtime.prepare()
        self.assertEqual(runtime.status(), RuntimeStatus.PREPARED)

        # Add runtime cleanup to clean it if test goes wrong
        def _clean_up_runtime():
            if runtime.status() != RuntimeStatus.TORN_DOWN:
                runtime.clean_up()
        self.addCleanup(_clean_up_runtime)

        # Start container
        yield runtime.start()
        self.assertEqual(runtime.status(), RuntimeStatus.RUNNING)

        # Test stdin/stdout
        test_input = ["żółw\n", "źrebię\n", "liść\n"]
        stdout = runtime.stdout(encoding="utf-8")
        with runtime.stdin(encoding="utf-8") as stdin:
            for line in test_input:
                stdin.write(line)
        test_output = list(stdout)
        self.assertEqual(test_input, test_output)

        # Wait for exit and delete container
        yield runtime.wait_until_stopped()
        self.assertEqual(runtime.status(), RuntimeStatus.STOPPED)
        yield runtime.clean_up()
        self.assertEqual(runtime.status(), RuntimeStatus.TORN_DOWN)

    @inlineCallbacks
    def test_benchmark(self):
        Whitelist.add(self.env.BENCHMARK_IMAGE.split('/')[0])
        benchmark_result = yield self.env.run_benchmark()
        self.assertGreater(benchmark_result.performance, 0)

    @inlineCallbacks
    def test_ports(self):
        port = 3333
        runtime = self.env.runtime(DockerRuntimePayload(
            image="busybox",
            tag="latest",
            command=f"nc -l -k -p {port}",
            ports=[port],
        ))
        yield runtime.prepare()
        yield runtime.start()

        try:
            mhost, mport = runtime.get_port_mapping(port)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.assertEqual(0, sock.connect_ex((mhost, mport)))
            finally:
                sock.close()
        finally:
            yield runtime.stop()
            yield runtime.clean_up()

    @inlineCallbacks
    def test_memory_counter(self):
        mib = 1024 * 1024
        num_bytes = 10 * mib

        malloc_code = f"""
        #include <stdlib.h>
        #include <unistd.h>

        int main(void) {{
            int i, n = {num_bytes};
            char * ptr;
            ptr = (char *) malloc (n);
            ptr[0] = 1;
            for (i = 1; i < n; ++i) {{
                ptr[i] = ptr[i-1];
            }}
            sleep(5);
            free(ptr);
            return 0;
        }}
        """

        Whitelist.add("frolvlad/alpine-gcc")
        installed = yield self.env.install_prerequisites(DockerPrerequisites(
            image="frolvlad/alpine-gcc",
            tag="latest"
        ))
        self.assertTrue(installed)

        runtime = self.env.runtime(DockerRuntimePayload(
            image="frolvlad/alpine-gcc",
            tag="latest",
            command="sh -c 'gcc -O0 -o x.exe -xc - ; ./x.exe'"
        ))
        yield runtime.prepare()
        yield runtime.start()
        try:
            stdin = runtime.stdin(encoding="utf-8")
            stdin.write(malloc_code)
            stdin.close()
            yield runtime.wait_until_stopped()

            avg_ram = runtime.usage_counter_values().ram_avg_bytes
            max_ram = runtime.usage_counter_values().ram_max_bytes
            self.assertLessEqual(avg_ram, max_ram)
            self.assertGreater(max_ram, num_bytes)
            # Upper bound is very loose because it is highly unpredictable
            self.assertLess(max_ram, 10 * num_bytes)
        finally:
            yield runtime.clean_up()

    @inlineCallbacks
    def test_cpu_counter(self):
        seconds = 10
        sec_ns = 1_000_000_000
        runtime = self.env.runtime(DockerRuntimePayload(
            image="busybox",
            tag="latest",
            command=f"sh -c '(dd if=/dev/zero of=/dev/null) & pid=$! ; "
                    f"sleep {seconds} ; kill $pid'"
        ))
        yield runtime.prepare()
        yield runtime.start()
        yield runtime.wait_until_stopped()
        try:
            cpu_user = runtime.usage_counter_values().cpu_user_ns
            cpu_kernel = runtime.usage_counter_values().cpu_kernel_ns
            cpu_total = runtime.usage_counter_values().cpu_total_ns
            self.assertApproximates(
                (cpu_user + cpu_kernel), cpu_total, 0.1 * sec_ns)
            self.assertGreater(cpu_total, 0.9 * seconds * sec_ns)
            # Upper bound is very loose because it is highly unpredictable
            self.assertLess(cpu_total, 10 * seconds * sec_ns)
        finally:
            yield runtime.clean_up()
