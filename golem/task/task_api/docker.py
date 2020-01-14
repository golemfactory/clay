from pathlib import Path
import os
from typing import Optional, Dict, Any
import json

from golem_task_api import constants as api_constants

from golem.core.common import is_windows
from golem.envs import Prerequisites, RuntimePayload
from golem.envs.docker import (
    DockerBind,
    DockerPrerequisites,
    DockerRuntimePayload,
)
from golem.task.task_api import TaskApiPayloadBuilder


class DockerTaskApiPayloadBuilder(TaskApiPayloadBuilder):
    @classmethod
    def create_payload(
            cls,
            prereq: Prerequisites,
            shared_dir: Path,
            command: str,
            port: int,
    ) -> RuntimePayload:
        assert isinstance(prereq, DockerPrerequisites)
        if prereq.extra_vars:
            extra_vars = json.loads(prereq.extra_vars)
            extra_options = extra_vars if extra_vars else {}
        else:
            extra_options = {}
        return DockerRuntimePayload(
            image=prereq.image,
            tag=prereq.tag,
            command=command,
            ports=[port],
            binds=[DockerBind(
                source=shared_dir,
                target=f'/{api_constants.WORK_DIR}',
            )],
            user=None if is_windows() else str(os.getuid()),
            **extra_options
        )
