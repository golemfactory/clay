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
        self._discovered: List[DiscoveredDockerImage] = list()

    def _docker_image_discovered(
            self,
            name: str
    ) -> None:
        if Whitelist.is_whitelisted(name):
            return
        for discovered in self._discovered:
            if discovered.name == name:
                discovered.appeared()
                return

        discovered_image = DiscoveredDockerImage(name)
        self._discovered.append(discovered_image)
        self._docker_refresh_discovered_images()

        EventPublisher.publish(
            Environment.evt_prereq_discovered,
            asdict(discovered_image),
            'docker')

    def _docker_refresh_discovered_images(self) -> None:
        """ Update the internal discovered Docker image collection based on
            Whitelist status and the number of MAX_DISCOVERED_IMAGES stored """
        self._discovered = [
            discovered for discovered in self._discovered
            if not Whitelist.is_whitelisted(
                repository_from_image_name(discovered.name))
        ]
        self._discovered = self._discovered[-MAX_DISCOVERED_IMAGES:]

    @rpc_utils.expose('env.docker.images.discovered')
    def _docker_discovered_get(self) -> Dict[str, Dict[str, Any]]:
        return {
            discovered.name: asdict(discovered)
            for discovered in self._discovered
        }

    @staticmethod
    @rpc_utils.expose('env.docker.images.whitelist')
    def _docker_whitelist_get() -> List[str]:
        return Whitelist.get()

    @rpc_utils.expose('env.docker.images.whitelist.add')
    def _docker_whitelist_add(self, image_name: str) -> None:
        repository = repository_from_image_name(image_name)
        Whitelist.add(repository)
        self._docker_refresh_discovered_images()

    @staticmethod
    @rpc_utils.expose('env.docker.images.whitelist.remove')
    def _docker_whitelist_remove(image_name: str) -> None:
        repository = repository_from_image_name(image_name)
        Whitelist.remove(repository)
