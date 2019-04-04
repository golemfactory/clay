from pathlib import Path
from typing import NamedTuple, Optional, List, Dict, Any

from golem.core.common import posix_path
from golem.envs import Payload, Serializable, Prerequisites


class DockerBindData(NamedTuple):
    source: Path
    target: str
    mode: str = 'rw'


class DockerBind(DockerBindData, Serializable):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        dict_ = self._asdict()
        dict_['source'] = str(dict_['source'])
        return dict_

    @classmethod
    def from_dict(cls, dict_: Dict[str, Any]) -> 'DockerBind':
        source = Path(dict_.pop('source'))
        return DockerBind(source=source, **dict_)

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

    @classmethod
    def from_dict(cls, dict_: Dict[str, Any]) -> 'DockerPayload':
        args = dict_.pop('args', [])
        env = dict_.pop('env', {})
        binds = [DockerBind.from_dict(b) for b in dict_.pop('binds', [])]
        return DockerPayload(args=args, env=env, binds=binds, **dict_)


class DockerPrerequisitesData(NamedTuple):
    image: str
    tag: str


class DockerPrerequisites(DockerPrerequisitesData, Prerequisites):
    """ This exists because NamedTuple must be single superclass """

    def to_dict(self) -> Dict[str, Any]:
        return self._asdict()

    @classmethod
    def from_dict(cls, dict_: Dict[str, Any]) -> 'DockerPrerequisites':
        return DockerPrerequisites(**dict_)
