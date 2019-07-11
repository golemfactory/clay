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
class TestIntegration(TestCase, DatabaseFixture):

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

    @inlineCallbacks
    def tearDown(self):
        yield self.env.clean_up()
        DatabaseFixture.tearDown(self)

    @pytest.mark.timeout(120)  # 120 sec should be well enough for this test
    @inlineCallbacks
    def test_io(self):
        # Download image
        Whitelist.add("busybox")
        installed = yield self.env.install_prerequisites(DockerPrerequisites(
            image="busybox",
            tag="latest"
        ))
        self.assertTrue(installed)

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
        score = yield self.env.run_benchmark()
        self.assertGreater(score, 0)

    @inlineCallbacks
    def test_ports(self):
        Whitelist.add("busybox")
        installed = yield self.env.install_prerequisites(DockerPrerequisites(
            image="busybox",
            tag="latest"
        ))
        self.assertTrue(installed)

        port = 4444
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
