from typing import NamedTuple, Optional, Dict, Any

from golem.envs import Payload, Prerequisites


class DockerPayloadData(NamedTuple):
    image: str
    tag: str
    env: Dict[str, str]
    command: Optional[str] = None
    user: Optional[str] = None
    work_dir: Optional[str] = None


class DockerPayload(DockerPayloadData, Payload):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DockerPayload':
        data = data.copy()
        env = data.pop('env', {})
        return DockerPayload(env=env, **data)


class DockerPrerequisitesData(NamedTuple):
    image: str
    tag: str


class DockerPrerequisites(DockerPrerequisitesData, Prerequisites):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DockerPrerequisites':
        return DockerPrerequisites(**data)
