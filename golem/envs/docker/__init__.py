from pathlib import Path
from typing import NamedTuple, Optional, Dict, Any, List

from golem.core.common import posix_path
from golem.envs import RuntimePayload, Prerequisites


class DockerBind(NamedTuple):
    source: Path
    target: str
    mode: str = 'rw'

    @property
    def source_as_posix(self) -> str:
        return posix_path(str(self.source))


class DockerRuntimePayloadData(NamedTuple):
    """ This exists because NamedTuple must be single superclass """
    image: str
    tag: str
    command: Optional[str] = None
    ports: Optional[List[int]] = None
    env: Optional[Dict[str, str]] = None
    user: Optional[str] = None
    work_dir: Optional[str] = None
    binds: Optional[List[DockerBind]] = None


class DockerRuntimePayload(DockerRuntimePayloadData, RuntimePayload):
    pass


class DockerPrerequisitesData(NamedTuple):
    """ This exists because NamedTuple must be single superclass """
    image: str
    tag: str


class DockerPrerequisites(DockerPrerequisitesData, Prerequisites):
    def to_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DockerPrerequisites':
        return DockerPrerequisites(**data)
