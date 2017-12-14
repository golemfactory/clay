import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from copy import deepcopy


logger = logging.getLogger('golem.network.upnp')


class IPortMapper(ABC):

    name = None

    @property
    @abstractmethod
    def available(self) -> bool:
        pass

    @property
    @abstractmethod
    def network(self) -> dict:
        pass

    @abstractmethod
    def discover(self) -> None:
        pass

    @abstractmethod
    def create_mapping(self,
                       local_port: int,
                       external_port: int = None,
                       protocol: str = 'TCP',
                       lease_duration: int = None) -> Optional[int]:
        pass

    @abstractmethod
    def remove_mapping(self,
                       external_port: int,
                       protocol: str = 'TCP') -> bool:
        pass


class PortMapperManager(IPortMapper):

    def __init__(self, mappers=None):
        from golem.network.upnp.igd import IGDPortMapper

        self._mappers = mappers or [IGDPortMapper()]
        self._active_mapper = None

        self._mapping = {
            'TCP': dict(),
            'UDP': dict()
        }
        self._network = {
            'local_ip_address': None,
            'external_ip_address': None,
            'connection_type': None,
            'status_info': None
        }

    @property
    def available(self) -> bool:
        return bool(self._active_mapper)

    @property
    def network(self) -> dict:
        if self.available:
            return self._active_mapper.network
        return dict()

    @property
    def mapping(self) -> Dict[str, Dict[int, int]]:
        return deepcopy(self._mapping)

    def discover(self):
        for mapper in self._mappers:
            logger.info('%s: starting discovery', mapper.name)

            try:
                mapper.discover()
            except Exception as exc:
                logger.warning('%s: discovery error: %s', mapper.name, exc)
                continue

            if mapper.available:
                self._active_mapper = mapper
                logger.info('%s: discovery complete', mapper.name)
                logger.info('%s: network configuration %r',
                            mapper.name, mapper.network)
                break

            logger.warning('%s-compatible device was not found', mapper.name)

    def create_mapping(self,
                       local_port: int,
                       external_port: int = None,
                       protocol: str = 'TCP',
                       lease_duration: int = None) -> Optional[int]:

        if not self.available:
            return None

        mapper = self._active_mapper

        try:
            port = mapper.create_mapping(local_port, external_port,
                                         protocol, lease_duration)
        except Exception as exc:
            logger.warning('%s: cannot map port %u (%s): %s',
                           mapper.name, local_port, protocol, exc)
        else:
            logger.info('%s: mapped %u -> %u (%s)',
                        mapper.name, local_port, port, protocol)
            return port

    def remove_mapping(self,
                       external_port: int,
                       protocol: str = 'TCP') -> bool:

        if not self.available:
            return False

        mapper = self._active_mapper

        try:
            mapper.remove_mapping(external_port, protocol)
        except Exception as exc:
            logger.warning('%s: cannot remove external port %u (%s) mapping: '
                           '%r', mapper.name, external_port, protocol, exc)
            return False

        logger.info('%s: removed external port mapping %u (%s)',
                    self._active_mapper.name, external_port, protocol)
        return True

    def update_node(self, node: 'Node') -> None:
        mapping = self._mapping['TCP']
        node.pub_port = mapping.get(node.prv_port, node.pub_port)
        node.p2p_pub_port = mapping.get(node.p2p_prv_port, node.p2p_pub_port)

    def quit(self) -> None:
        if not self.available:
            return

        for protocol, mapping in self._mapping.items():
            for external_ip in mapping.values():
                self.remove_mapping(external_ip, protocol)
