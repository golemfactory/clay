import tempfile
import time
from pathlib import Path

import pytest
from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from golem.envs import EnvStatus, RuntimeStatus
from golem.envs.docker import DockerPrerequisites, DockerPayload
from golem.envs.docker.cpu import DockerCPUConfig, DockerCPUEnvironment
from golem.tools.ci import ci_skip


@ci_skip
class TestIntegration(TestCase):

    @pytest.mark.timeout(60)  # 60 sec should be well enough for this test
    @inlineCallbacks
    def test_io(self):
        # Set up environment
        config = DockerCPUConfig(work_dir=Path(tempfile.gettempdir()))
        env = DockerCPUEnvironment(config)
        yield env.prepare()
        self.assertEqual(env.status(), EnvStatus.ENABLED)

        # Download image
        yield env.install_prerequisites(DockerPrerequisites(
            image="busybox",
            tag="latest"
        ))

        # Create runtime
        runtime = env.runtime(DockerPayload(
            image="busybox",
            tag="latest",
            binds=[],
            env={},
            command="sh -c 'cat -'"
        ))

        # Start container
        yield runtime.prepare()
        self.assertEqual(runtime.status(), RuntimeStatus.PREPARED)
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
        yield runtime.cleanup()
        self.assertEqual(runtime.status(), RuntimeStatus.TORN_DOWN)
