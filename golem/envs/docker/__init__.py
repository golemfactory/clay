from pathlib import Path
from typing import NamedTuple, Optional, List, Dict, Any

from golem.core.common import posix_path
from golem.core.simpleserializer import DictSerializable
from golem.envs import Payload, Prerequisites


class DockerBindData(NamedTuple):
    source: Path
    target: str
    mode: str = 'rw'


class DockerBind(DockerBindData, DictSerializable):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        dict_ = self._asdict()
        dict_['source'] = str(dict_['source'])
        return dict_

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DockerBind':
        data = data.copy()
        source = Path(data.pop('source'))
        return DockerBind(source=source, **data)

    @property
    def source_as_posix(self) -> str:
        return posix_path(str(self.source))


class DockerPayloadData(NamedTuple):
    image: str
    tag: str
    args: List[str]
    binds: List[DockerBind]
    env: Dict[str, str]
    command: Optional[str] = None
    user: Optional[str] = None
    work_dir: Optional[str] = None


class DockerPayload(DockerPayloadData, Payload):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        dict_ = self._asdict()
        dict_['binds'] = [bind.to_dict() for bind in dict_['binds']]
        return dict_

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DockerPayload':
        data = data.copy()
        args = data.pop('args', [])
        env = data.pop('env', {})
        binds = [DockerBind.from_dict(b) for b in data.pop('binds', [])]
        return DockerPayload(args=args, env=env, binds=binds, **data)


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
