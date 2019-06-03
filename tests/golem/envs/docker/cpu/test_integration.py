import tempfile
import time
from pathlib import Path

import pytest
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from golem.envs import EnvStatus, RuntimeStatus
from golem.envs.docker import DockerPrerequisites, DockerPayload
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.envs.docker.whitelist import Whitelist
from golem.testutils import DatabaseFixture
from golem.tools.ci import ci_skip


@ci_skip
class TestIntegration(TestCase, DatabaseFixture):

    @pytest.mark.timeout(60)  # 60 sec should be well enough for this test
    @inlineCallbacks
    def test_io(self):
        # Set up environment
        config = DockerCPUConfig(work_dir=Path(tempfile.gettempdir()))
        env = DockerCPUEnvironment(config)
        yield env.prepare()
        self.assertEqual(env.status(), EnvStatus.ENABLED)

        # Add environment cleanup to clean it if test goes wrong
        def _clean_up_env():
            if env.status() != EnvStatus.DISABLED:
                env.clean_up()
        self.addCleanup(_clean_up_env)

        # Download image
        Whitelist.add("busybox")
        installed = yield env.install_prerequisites(DockerPrerequisites(
            image="busybox",
            tag="latest"
        ))
        self.assertTrue(installed)

        # Create runtime
        runtime = env.runtime(DockerPayload(
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
        while runtime.status() == RuntimeStatus.RUNNING:
            time.sleep(1)
        self.assertEqual(runtime.status(), RuntimeStatus.STOPPED)
        yield runtime.clean_up()
        self.assertEqual(runtime.status(), RuntimeStatus.TORN_DOWN)

        # Clean up the environment
        yield env.clean_up()
        self.assertEqual(env.status(), EnvStatus.DISABLED)
