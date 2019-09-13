import enum
import json
import logging
import os
from typing import Iterable, Optional

from crossbar.common.checkconfig import check_config
from crossbar.personality import Personality
from twisted.internet.defer import inlineCallbacks

from golem.rpc import cert
from golem.rpc.common import CROSSBAR_DIR, CROSSBAR_REALM, CROSSBAR_HOST, \
    CROSSBAR_PORT
from golem.rpc.mapping.rpcmethodnames import DOCKER_URI
from golem.rpc.session import WebSocketAddress

logger = logging.getLogger('golem.rpc.crossbar')


# pylint: disable=too-many-instance-attributes
class CrossbarRouter(object):
    serializers = ['msgpack']

    @enum.unique
    class CrossbarRoles(enum.Enum):
        admin = enum.auto()
        docker = enum.auto()

    # pylint: disable=too-many-arguments
    def __init__(self,
                 datadir: str,
                 host: Optional[str] = CROSSBAR_HOST,
                 port: Optional[int] = CROSSBAR_PORT,
                 realm: str = CROSSBAR_REALM,
                 ssl: bool = True,
                 generate_secrets: bool = False) -> None:

        self.working_dir = os.path.join(datadir, CROSSBAR_DIR)

        os.makedirs(self.working_dir, exist_ok=True)
        if not os.path.isdir(self.working_dir):
            raise IOError("'{}' is not a directory".format(self.working_dir))

        self.cert_manager = cert.CertificateManager(self.working_dir)
        if generate_secrets:
            self.cert_manager.generate_secrets()

        self.address = WebSocketAddress(host, port, realm, ssl)

        self.node = None
        self.pubkey = None
        self.personality_cls = Personality

        self.config = self._build_config(address=self.address,
                                         serializers=self.serializers,
                                         cert_manager=self.cert_manager)

        check_config(self.personality_cls, self.config)
        logger.debug('xbar init with cfg: %s', json.dumps(self.config))

    def start(self, reactor):
        # imports reactor
        from crossbar.node.node import Node

        if self.address.ssl:
            self.cert_manager.generate_if_needed()

        self.node = Node(personality=self.personality_cls,
                         cbdir=self.working_dir,
                         reactor=reactor)

        self.node.load_keys(self.working_dir)
        self.node.load_config(None, self.config)

        return self.node.start()

    @inlineCallbacks
    def stop(self):
        yield self.node.stop()

    @staticmethod
    def _users_config(cert_manager: cert.CertificateManager):
        # configuration for crsb_users with admin priviliges
        admin_role: str = CrossbarRouter.CrossbarRoles.admin.name
        docker_role: str = CrossbarRouter.CrossbarRoles.docker.name

        user_roles = {
            cert_manager.CrossbarUsers.golemapp: admin_role,
            cert_manager.CrossbarUsers.golemcli: admin_role,
            cert_manager.CrossbarUsers.electron: admin_role,
            cert_manager.CrossbarUsers.docker: docker_role,
        }

        crsb_users = {}
        for user, role in user_roles.items():
            entry = {}
            entry['secret'] = cert_manager.get_secret(user)
            entry['role'] = role
            crsb_users[user.name] = entry

        return crsb_users

    @staticmethod
    def _build_config(address: WebSocketAddress,
                      serializers: Iterable[str],
                      cert_manager: cert.CertificateManager,
                      realm: str = CROSSBAR_REALM,
                      enable_webstatus: bool = False):

        allowed_origins = [
            'http://' + address.host + ':*',
            'https://' + address.host + ':*'
        ]

        ws_endpoint = {
            'type': 'tcp',
            'interface': address.host,
            'port': address.port,
        }

        if address.ssl:
            ws_endpoint["tls"] = {
                "key": cert_manager.key_path,
                "certificate": cert_manager.cert_path,
                "dhparam": cert_manager.dh_path,
            }

        return {
            'version': 2,
            'controller': {
                'options': {
                    'shutdown': ['shutdown_on_shutdown_requested'],
                }
            },
            'workers': [{
                'type': 'router',
                'options': {
                    'title': 'Golem'
                },
                'transports': [{
                    'type': 'websocket',
                    'serializers': serializers,
                    'endpoint': ws_endpoint,
                    'url': str(address),
                    'options': {
                        'allowed_origins': allowed_origins,
                        'enable_webstatus': enable_webstatus,
                    },
                    "auth": {
                        "wampcra": {
                            "type": "static",
                            "users": CrossbarRouter._users_config(cert_manager)
                        }
                    }
                }],
                'components': [],
                "realms": [{
                    "name": realm,
                    "roles": [
                        {
                            "name": CrossbarRouter.CrossbarRoles.admin.name,
                            "permissions": [{
                                "uri": '*',
                                "allow": {
                                    "call": True,
                                    "register": True,
                                    "publish": True,
                                    "subscribe": True
                                }
                            }]
                        },
                        {
                            "name": CrossbarRouter.CrossbarRoles.docker.name,
                            "permissions": [
                                {
                                    "uri": '*',
                                    "allow": {
                                        "call": False,
                                        "register": False,
                                        "publish": False,
                                        "subscribe": False
                                    }
                                },
                                {
                                    # more specific config takes precedence
                                    "uri": f'{DOCKER_URI}.*',
                                    "allow": {
                                        "call": True,
                                        "register": False,
                                        "publish": False,
                                        "subscribe": False
                                    }
                                },
                                {
                                    "uri": 'sys.exposed_procedures',
                                    "allow": {
                                        "call": True,
                                        "register": False,
                                        "publish": False,
                                        "subscribe": False
                                    },
                                },
                            ]
                        }]
                }],
            }]
        }
