import copy
import logging
import threading

from apps.core.task.coretask import CoreTask
from apps.core.task.coretaskstate import TaskDefinition
from golem.task.taskbase import AcceptClientVerdict


logger = logging.getLogger(__name__)


class ManualTask(CoreTask):
    def __init__(self, task_definition: TaskDefinition,
                 owner: 'dt_p2p.Node', **kwargs):
        super().__init__(task_definition, owner)
        self.nominated_providers = set()
        self.declared_providers = set()
        self.lock = threading.Lock()

    def should_accept_client(self,
                             node_id: str,
                             offer_hash: str) -> AcceptClientVerdict:

        with self.lock:
            verdict = super().should_accept_client(node_id, offer_hash)
            if verdict == AcceptClientVerdict.REJECTED:
                self.declared_providers.remove(node_id)
                self.nominated_providers.remove(node_id)
                return verdict
                # We allow to decide owner of task (requestor) to decide whether
                # accept the specific provider unless the provider is rejected.
            self.declared_providers.add(node_id)
            logger.info('Declared nodes are: {}, nominated nodes are: {}'.format(self.declared_providers,
                                                                                 self.nominated_providers))
            if node_id in self.nominated_providers:
                logger.info('Node {} is nominated so we accept it'.format(node_id))
                return AcceptClientVerdict.ACCEPTED
            return AcceptClientVerdict.SHOULD_WAIT

    def get_declared_providers(self,):
        with self.lock:
            return self.declared_providers - self.nominated_providers

    def nominate_provider(self, node_id):
        with self.lock:
            self.nominated_providers.add(node_id)

    def is_provider_declared(self, node_id):
        with self.lock:
            return node_id in self.declared_providers

    def __getstate__(self):
        state = super().__getstate__()
        del state['lock']
        state['nominated_providers'] = copy.deepcopy(self.nominated_providers)
        return state

    def __setstate__(self, state):
        super().__setstate__(state)
        self.lock = threading.Lock()
        self.declared_providers = copy.deepcopy(self.nominated_providers)
