from pathlib import Path
from typing import NamedTuple, Optional, List, Dict

from golem.core.common import posix_path


class DockerBind(NamedTuple):
    source: Path
    target: str
    mode: str = 'rw'

    @property
    def source_as_posix(self) -> str:
        return posix_path(str(self.source))


class DockerPayload(NamedTuple):
    image: str
    tag: str
    args: List[str]
    binds: List[DockerBind]
    env: Dict[str, str]
    command: Optional[str] = None
    user: Optional[str] = None
    work_dir: Optional[str] = None


class DockerPrerequisites(NamedTuple):
    image: str
    tag: str
