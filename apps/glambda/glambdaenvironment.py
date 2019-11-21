import filecmp
import logging
import shutil
from typing import Dict

from golem.core.common import is_linux
from golem.docker.environment import DockerEnvironment
from golem.environments.environment import SupportStatus, UnsupportReason

logger = logging.getLogger(__name__)


class GLambdaTaskEnvironment(DockerEnvironment):
    DOCKER_IMAGE = "golemfactory/glambda"
    DOCKER_TAG = "1.7.1"
    ENV_ID = "glambda"
    SHORT_DESCRIPTION = "GLambda PoC"

    def check_support(self) -> SupportStatus:
        GVISOR_SECURE_RUNTIME = 'runsc'
        if is_linux():
            if not shutil.which(GVISOR_SECURE_RUNTIME):
                return SupportStatus.err({
                    UnsupportReason.ENVIRONMENT_NOT_SECURE: self.ENV_ID
                })
            if not GLambdaTaskEnvironment._is_cgroup_cpuset_cfg_correct():
                logger.warning('Unable to start GLambda app. Setting '
                               '`cgroup.cpuset.cpus` does not match `docker.'
                               'cpuset.cpus`. Potential fix: `cat /sys/fs/'
                               'cgroup/cpuset/cpuset.cpus > /sys/fs/cgroup/'
                               'cpuset/docker/cpuset.cpus`.')
                return SupportStatus.err({
                    UnsupportReason.ENVIRONMENT_MISCONFIGURED: self.ENV_ID
                })
        return super().check_support()

    @staticmethod
    def _is_cgroup_cpuset_cfg_correct():
        try:
            res = filecmp.cmp('/sys/fs/cgroup/cpuset/cpuset.cpus',
                              '/sys/fs/cgroup/cpuset/docker/cpuset.cpus')
        except FileNotFoundError:
            return False
        return res

    def get_container_config(self) -> Dict:
        return dict(
            runtime='runsc' if is_linux() else None,
            volumes=[],
            binds={},
            devices=[],
            # gVisor uses HOME variable before starting the image.
            # Starting docker as a particular user (docker --user parameter)
            # does not set HOME and that's why we define it here.
            environment={'HOME': '/home/user'} if is_linux() else {}
        )
