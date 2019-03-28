import shutil
from typing import Dict

from golem.core.common import is_linux
from golem.docker.environment import DockerEnvironment
from golem.environments.environment import SupportStatus, UnsupportReason


class GLambdaTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/glambda"
    DOCKER_TAG = "1.3"
    ENV_ID = "glambda"
    SHORT_DESCRIPTION = "GLambda PoC"

    def check_support(self) -> SupportStatus:
        GVISOR_SECURE_RUNTIME = 'runsc'
        if is_linux() and not shutil.which(GVISOR_SECURE_RUNTIME):
            return SupportStatus.err({
                UnsupportReason.ENVIRONMENT_NOT_SECURE: self.ENV_ID
            })
        return super().check_support()

    def get_container_config(self) -> Dict:
        return dict(
            runtime='runsc' if is_linux() else None,
            volumes=[],
            binds={},
            devices=[],
            environment={}
        )
