from typing import Any, Dict, List

from dataclasses import dataclass, field, asdict

from golem.core.common import get_timestamp_utc
from golem.envs.docker.whitelist import Whitelist, repository_from_image_name
from golem.report import EventPublisher
from golem.rpc import utils as rpc_utils
from golem.rpc.mapping.rpceventnames import Environment

MAX_DISCOVERED_IMAGES: int = 50


@dataclass
class DiscoveredDockerImage:
    name: str
    discovery_ts: float = field(default_factory=get_timestamp_utc)
    last_seen_ts: float = field(default_factory=get_timestamp_utc)
    times_seen: int = 1

    def appeared(self) -> None:
        self.last_seen_ts = get_timestamp_utc()
        self.times_seen += 1


class DockerWhitelistRPC:
    def __init__(self) -> None:
        self._discovered: Dict[str, DiscoveredDockerImage] = dict()

    def _docker_image_discovered(
            self,
            name: str
    ) -> None:
        if Whitelist.is_whitelisted(name):
            return
        if name in self._discovered:
            self._discovered[name].appeared()
            return

        discovered_image = DiscoveredDockerImage(name)
        self._discovered[name] = discovered_image
        self._docker_refresh_discovered_images()

        EventPublisher.publish(
            Environment.evt_prereq_discovered,
            asdict(discovered_image),
            'docker')

    def _docker_refresh_discovered_images(self) -> None:
        """ Update the internal discovered Docker image collection based on
            Whitelist status and the number of MAX_DISCOVERED_IMAGES stored """
        self._discovered = {
            name: discovered
            for name, discovered in self._discovered.items()
            if not Whitelist.is_whitelisted(name)
        }

        while len(self._discovered) > MAX_DISCOVERED_IMAGES:
            first_key = next(iter(self._discovered.keys()))
            del self._discovered[first_key]

    @rpc_utils.expose('env.docker.images.discovered')
    def _docker_discovered_get(self) -> Dict[str, Dict[str, Any]]:
        return {
            key: asdict(value)
            for key, value in self._discovered.items()
        }

    @staticmethod
    @rpc_utils.expose('env.docker.repos.whitelist')
    def _docker_whitelist_get_all() -> List[str]:
        return Whitelist.get_all()

    @rpc_utils.expose('env.docker.repos.whitelist.add')
    def _docker_whitelist_add(self, repository: str) -> None:
        Whitelist.add(repository)
        self._docker_refresh_discovered_images()

    @staticmethod
    @rpc_utils.expose('env.docker.repos.whitelist.remove')
    def _docker_whitelist_remove(repository: str) -> None:
        Whitelist.remove(repository)
