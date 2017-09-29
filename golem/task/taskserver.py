# -*- coding: utf-8 -*-
import datetime
import itertools
import logging
import os
import time

from pydispatch import dispatcher

from golem import model
from golem.core.async import async_run, AsyncRequest
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.ranking.helper.trust import Trust
from golem.task.deny import get_deny_set
from golem.task.taskbase import TaskHeader
from .taskcomputer import TaskComputer
from .taskkeeper import TaskHeaderKeeper
from .taskmanager import TaskManager

logger = logging.getLogger('golem.task.taskserver')


tmp_cycler = itertools.cycle(list(range(550)))


class TaskServer:
    def __init__(self, node,
                 config_desc: ClientConfigDescriptor(),
                 keys_auth,
                 client,
                 task_service,
                 use_ipv6=False,
                 use_docker_machine_manager=True):

        self.node = node
        self.client = client
        self.keys_auth = keys_auth
        self.config_desc = config_desc

        self.task_keeper = TaskHeaderKeeper(
            client.environments_manager,
            min_price=config_desc.min_price
        )
        self.task_manager = TaskManager(
            config_desc.node_name,
            self.node,
            self.keys_auth,
            root_path=self.__get_task_manager_root(client.datadir),
            tasks_dir=os.path.join(client.datadir, 'tasks')
        )
        self.task_computer = TaskComputer(
            config_desc.node_name,
            task_server=self,
            use_docker_machine_manager=use_docker_machine_manager
        )

        self.task_manager.listen_address =\
            self.node.pub_addr or self.node.prv_addr
        self.task_manager.listen_port = self.client.get_p2p_port()
        self.task_manager.node = self.node
        self.task_service = task_service

        self.task_sessions = {}

        self.max_trust = 1.0
        self.min_trust = 0.0

        self.last_messages = []
        self.last_message_time_threshold = config_desc.task_session_timeout

        self.results_to_send = {}
        self.failures_to_send = {}
        self.payments_to_send = set()
        self.payment_requests_to_send = set()

        self.deny_set = get_deny_set(datadir=client.datadir)

        dispatcher.connect(self.paymentprocessor_listener,
                           signal="golem.paymentprocessor")
        dispatcher.connect(self.transactions_listener,
                           signal="golem.transactions")

    def paymentprocessor_listener(self, sender, signal, event='default', **kwargs):
        if event != 'payment.confirmed':
            return
        payment = kwargs.pop('payment')
        logging.debug('Notified about payment.confirmed: %r', payment)
        self.payments_to_send.add(payment)

    def transactions_listener(self, sender, signal, event='default', **kwargs):
        if event != 'expected_income':
            return
        expected_income = kwargs.pop('expected_income')
        logger.debug('REQUESTS_TO_SEND: expected_income')
        self.payment_requests_to_send.add(expected_income)

    def key_changed(self):
        """React to the fact that key id has been changed. Inform task manager about new key """
        self.task_manager.key_id = self.keys_auth.get_key_id()

    def change_config(self, config_desc, run_benchmarks=False):
        self.config_desc = config_desc
        self.last_message_time_threshold = config_desc.task_session_timeout
        self.task_manager.change_config(self.__get_task_manager_root(self.client.datadir))
        self.task_computer.change_config(config_desc, run_benchmarks=run_benchmarks)
        self.task_keeper.change_config(config_desc)

    def sync_network(self):
        self.send_waiting_results()
        self.send_waiting_payments()
        self.send_waiting_payment_requests()
        self.task_computer.run()
        self.__remove_old_tasks()

        if next(tmp_cycler) == 0:
            logger.debug('TASK SERVER TASKS DUMP: %r',
                         self.task_manager.tasks)
            logger.debug('TASK SERVER TASKS STATES: %r',
                         self.task_manager.tasks_states)

    def quit(self):
        self.task_computer.quit()

    def get_environment_by_id(self, env_id):
        return self.task_keeper.environments_manager.get_environment_by_id(env_id)

    # This method chooses random task from the network to compute on our machine
    def request_task(self):
        theader = self.task_keeper.get_task()
        if not isinstance(theader, TaskHeader):
            return None

        task_id = theader.task_id
        owner_id = theader.task_owner_key_id
        max_price = theader.max_price

        if not self.should_accept_requestor(owner_id):
            return None
        if self.config_desc.min_price > max_price:
            return None

        env = self.get_environment_by_id(theader.environment)
        performance = env.get_performance(self.config_desc) or 0.0
        address = (theader.task_owner_address, theader.task_owner_port)
        eth_account = None

        transaction_system = self.client.transaction_system
        if transaction_system:
            eth_account = transaction_system.get_payment_address()

        kwargs = {
            'task_id': task_id,
            'performance': performance,
            'price': self.config_desc.min_price,
            'max_disk': self.config_desc.max_resource_size,
            'max_memory': self.config_desc.max_memory_size,
            'max_cpus': self.config_desc.num_cores,
            'eth_account': eth_account
        }

        try:

            self.task_manager.add_comp_task_request(theader, int(max_price))
            self.task_service.spawn_connect(
                owner_id,
                [address],
                lambda session: self._request_task_success(session, **kwargs),
                lambda error: self._request_task_error(error, task_id)
            )

            return task_id

        except Exception as err:
            self._request_task_error(err, task_id)

    def _request_task_success(self, session, **args):
        task_id = args['task_id']
        self.task_sessions[task_id] = session
        self.task_service.send_task_request(session, **args)

    def _request_task_error(self, error, task_id):
        self.task_computer.task_request_rejected(task_id, "Connection failed")
        self.task_computer.session_timeout()
        self.task_keeper.remove_task_header(task_id)
        self.task_manager.comp_task_keeper.request_failure(task_id)
        logger.warning("Request failed for task {}: {}"
                       .format(task_id, error))

    def send_task_failed(self, subtask_id, task_id, err_msg, owner):
        Trust.REQUESTED.decrease(owner.key)

        if subtask_id not in self.failures_to_send:
            self.failures_to_send[subtask_id] = WaitingTaskFailure(
                task_id, subtask_id, err_msg, owner
            )

    def pull_resources(self, task_id, resources, client_options=None):
        self.client.pull_resources(task_id, resources,
                                   client_options=client_options)

    def send_result(self, subtask_id, task_id, computing_time, result, owner):

        if subtask_id in self.results_to_send:
            raise RuntimeError("Unknown subtask_id: {}".format(subtask_id))

        Trust.REQUESTED.increase(owner.key)

        task_result_manager = self.task_manager.task_result_manager
        comp_task_keeper = self.task_manager.comp_task_keeper
        value = comp_task_keeper.get_value(task_id, computing_time)

        if self.client.transaction_system:
            self.client.transaction_system.incomes_keeper.expect(
                sender_node_id=owner.key,
                p2p_node=owner,
                task_id=task_id,
                subtask_id=subtask_id,
                value=value,
            )

        resource_manager = task_result_manager.resource_manager
        resource_options = resource_manager.build_client_options(self.node.key)
        resource_secret = task_result_manager.gen_secret()

        def success(path_and_hash):
            logger.debug("Task server: task result: %r", path_and_hash)
            self.results_to_send[subtask_id] = WaitingTaskResult(
                task_id,
                subtask_id,
                computing_time,
                path_and_hash[1],
                resource_secret,
                resource_options,
                owner
            )

        def error(exc):
            logger.error("Couldn't create a task result package for "
                         "subtask %r: %r", subtask_id, exc)

            if isinstance(exc, EnvironmentError):
                self.retry_sending_task_result(subtask_id)
            else:
                self.send_task_failed(subtask_id, task_id, str(exc), owner)

        request = AsyncRequest(task_result_manager.create,
                               self.node,
                               # FIXME: introduced for backwards compatibility
                               TaskResultWrapper(task_id, subtask_id,
                                                 result, owner),
                               client_options=resource_options,
                               key_or_secret=resource_secret)

        async_run(request, success=success, error=error)
        return True

    def get_task_headers(self):
        ths = self.task_keeper.get_all_tasks() + \
              self.task_manager.get_task_headers()
        return ths #[th.to_dict() for th in ths]

    def add_task_header(self, th_dict_repr):
        try:
            if not self.verify_header_sig(th_dict_repr):
                raise Exception("Invalid signature")

            task_id = th_dict_repr["task_id"]
            key_id = th_dict_repr["task_owner_key_id"]
            task_ids = list(self.task_manager.tasks.keys())
            new_sig = True

            if task_id in self.task_keeper.task_headers:
                header = self.task_keeper.task_headers[task_id]
                new_sig = th_dict_repr["signature"] != header.signature

            if task_id not in task_ids and key_id != self.node.key and new_sig:
                self.task_keeper.add_task_header(th_dict_repr)

            return True
        except Exception as err:
            logger.warning("Wrong task header received {}".format(err))
            return False

    def remove_task_header(self, task_id):
        self.task_keeper.remove_task_header(task_id)

    def add_task_session(self, subtask_id, session):
        self.task_sessions[subtask_id] = session

    def remove_task_session(self, task_session):
        for key in list(self.task_sessions.keys()):
            if self.task_sessions[key] == task_session:
                self.task_sessions.pop(key)

    def encrypt(self, message, public_key):
        if public_key == 0:
            return message
        return self.keys_auth.encrypt(message, public_key)

    def decrypt(self, message):
        return self.keys_auth.decrypt(message)

    def sign(self, data):
        return self.keys_auth.sign(data)

    def verify_sig(self, sig, data, public_key):
        return self.keys_auth.verify(sig, data, public_key)

    def verify_header_sig(self, th_dict_repr):
        _bin = TaskHeader.dict_to_binary(th_dict_repr)
        _sig = th_dict_repr["signature"]
        _key = th_dict_repr["task_owner_key_id"]
        return self.verify_sig(_sig, _bin, _key)

    def get_subtask_ttl(self, task_id):
        return self.task_manager.comp_task_keeper.get_subtask_ttl(task_id)

    def task_result_sent(self, subtask_id):
        return self.results_to_send.pop(subtask_id, None)

    def retry_sending_task_result(self, subtask_id):
        wtr = self.results_to_send.get(subtask_id, None)
        if wtr:
            wtr.already_sending = False

    def change_timeouts(self, task_id, full_task_timeout, subtask_timeout):
        self.task_manager.change_timeouts(task_id, full_task_timeout, subtask_timeout)

    def get_task_computer_root(self):
        return os.path.join(self.client.datadir, "ComputerRes")

    def subtask_accepted(self, subtask_id, reward):
        logger.debug("Subtask {} result accepted".format(subtask_id))
        self.task_result_sent(subtask_id)

    def subtask_rejected(self, subtask_id):
        logger.debug("Subtask {} result rejected".format(subtask_id))
        self.task_result_sent(subtask_id)
        task_id = self.task_manager.comp_task_keeper.get_task_id_for_subtask(subtask_id)
        if task_id is not None:
            self.decrease_trust_payment(task_id)
            # self.remove_task_header(task_id)
            # TODO Inform transaction system and task manager about failed payment
        else:
            logger.warning("Not my subtask rejected {}".format(subtask_id))

    def subtask_failure(self, subtask_id, err):
        logger.info("Computation for task {} failed: {}.".format(subtask_id, err))
        node_id = self.task_manager.get_node_id_for_subtask(subtask_id)
        Trust.COMPUTED.decrease(node_id)
        self.task_manager.task_computation_failure(subtask_id, err)

    def accept_result(self, subtask_id, account_info):
        mod = min(max(self.task_manager.get_trust_mod(subtask_id), self.min_trust), self.max_trust)
        Trust.COMPUTED.increase(account_info.key_id, mod)

        task_id = self.task_manager.get_task_id(subtask_id)
        value = self.task_manager.get_value(subtask_id)
        if not value:
            logger.info("Invaluable subtask: %r value: %r", subtask_id, value)
            return

        if not self.client.transaction_system:
            logger.info("Transaction system not ready. Ignoring payment for subtask: %r", subtask_id)
            return

        if not account_info.eth_account.address:
            logger.warning("Unknown payment address of %r (%r). Subtask: %r", account_info.node_name, account_info.addr, subtask_id)
            return

        payment = self.client.transaction_system.add_payment_info(
            task_id, subtask_id, value, account_info)
        logger.debug('Result accepted for subtask: %s Created payment: %r', subtask_id, payment)
        return payment

    def reject_result(self, subtask_id, key_id):
        trust_mod = self.task_manager.get_trust_mod(subtask_id)
        mod = min(max(trust_mod, self.min_trust), self.max_trust)
        Trust.WRONG_COMPUTED.decrease(key_id, mod)

    # TRUST

    def increase_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.increase(node_id, self.max_trust)

    def decrease_trust_payment(self, task_id):
        node_id = self.task_manager.comp_task_keeper.get_node_for_task_id(task_id)
        Trust.PAYMENT.decrease(node_id, self.max_trust)

    def get_computing_trust(self, node_id):
        return self.client.get_computing_trust(node_id)

    def receive_subtask_computation_time(self, subtask_id, computation_time):
        self.task_manager.set_computation_time(subtask_id, computation_time)

    def should_accept_provider(self, node_id):
        if node_id in self.deny_set:
            return False
        trust = self.get_computing_trust(node_id)
        logger.debug("Computing trust level: {}".format(trust))
        return trust >= self.config_desc.computing_trust

    def should_accept_requestor(self, node_id):
        if node_id in self.deny_set:
            return False
        trust = self.client.get_requesting_trust(node_id)
        logger.debug("Requesting trust level: {}".format(trust))
        return trust >= self.config_desc.requesting_trust

    def reward_for_subtask_paid(self, subtask_id, reward, transaction_id,
                                block_number):
        logger.info(
            "Received payment for subtask %r (val:%r, tid:%r, bn:%r)",
            subtask_id,
            reward,
            transaction_id,
            block_number
        )
        try:
            expected_income = model.ExpectedIncome.get(subtask=subtask_id)
        except model.ExpectedIncome.DoesNotExist:
            logger.warning(
                'Received unexpected payment for subtask %r'
                '(val:%rGNT, tid: %r, bn:%r)',
                subtask_id,
                reward,
                transaction_id,
                block_number
            )
            return
        if expected_income.value != reward:
            logger.error(
                "Reward mismatch for subtask: %r. expected: %r got: %r",
                subtask_id,
                expected_income.value,
                reward
            )
            return
        task_id = expected_income.task
        node_id = expected_income.sender_node

        # check that the reward has been successfully written in db
        result = self.client.transaction_system.incomes_keeper.received(
            sender_node_id=node_id,
            task_id=task_id,
            subtask_id=subtask_id,
            transaction_id=transaction_id,
            block_number=block_number,
            value=reward,
        )

        # Trust is increased only after confirmation from incomes keeper
        from golem.model import Income
        if type(result) is Income:
            Trust.PAYMENT.increase(node_id, self.max_trust)

    def noop(self, *args, **kwargs):
        args_, kwargs_ = args, kwargs  # avoid params name collision in logger
        logger.debug('Noop(%r, %r)', args_, kwargs_)

    #############################
    # SYNC METHODS
    #############################
    def __remove_old_tasks(self):
        self.task_keeper.remove_old_tasks()
        nodes_with_timeouts = self.task_manager.check_timeouts()
        for node_id in nodes_with_timeouts:
            Trust.COMPUTED.decrease(node_id)

    def _send_waiting_payments(self, elems_set, cb):

        time_delta = datetime.timedelta(seconds=30)

        for elem in elems_set.copy():

            if hasattr(elem, '_last_try'):
                now = datetime.datetime.now()
                if now - elem._last_try < time_delta:
                    continue

            logger.debug('_send_waiting(): %r', elem)

            elem._last_try = datetime.datetime.now()
            subtask_id = elem.subtask
            session = self._find_sessions(subtask_id)

            logger.debug('_send_waiting() session :%r', session)

            if session:
                cb(session, elem)
                return

            p2p_node = elem.get_sender_node()
            if p2p_node is None:
                logger.debug('Empty node info in %r', elem)
                elems_set.discard(elem)
                continue

            self.task_service.spawn_connect(
                p2p_node.key,
                addresses=p2p_node.get_addresses(),
                cb=lambda session, e=elem: cb(session, e),
                eb=lambda error, e=elem: elems_set.discard(e)
            )

    def send_waiting_payment_requests(self):
        self._send_waiting_payments(
            elems_set=self.payment_requests_to_send,
            cb=self._send_waiting_payment_request
        )

    def _send_waiting_payment_request(self, session, payment):
        self.payment_requests_to_send.discard(payment)
        self.task_service.send_payment_request(session, payment.subtask)

    def send_waiting_payments(self):
        self._send_waiting_payments(
            elems_set=self.payments_to_send,
            cb=self._send_waiting_payment
        )

    def _send_waiting_payment(self, session, payment):
        self.payments_to_send.discard(payment)
        self.task_service.send_payment(session, payment.subtask)

    def send_waiting_results(self):
        self.send_results()
        self.send_failures()

    def send_results(self):
        for subtask_id in list(self.results_to_send.keys()):
            wtr = self.results_to_send[subtask_id]
            if not wtr.can_send():
                continue

            wtr.mark_sending()
            session = self.task_sessions.get(subtask_id)

            if session:
                self._send_result(session, wtr)
            else:
                self.task_service.spawn_connect(
                    wtr.owner.key,
                    addresses=wtr.owner.get_addresses(),
                    cb=lambda session, w=wtr: self._send_result(session, w),
                    eb=lambda error, w=wtr: self._send_result_failure(w)
                )

    def _send_result(self, session, wtr):
        self.task_sessions[wtr.subtask_id] = session
        self.results_to_send.pop(wtr.subtask_id, None)
        self.task_service.send_result(
            session,
            wtr.subtask_id,
            wtr.computing_time,
            wtr.resource_hash,
            wtr.resource_secret,
            wtr.resource_options
        )

    def _send_result_failure(self, wtr):
        wtr.reset(self.config_desc.max_results_sending_delay)

    def send_failures(self):
        for subtask_id in list(self.failures_to_send.keys()):
            wtf = self.failures_to_send[subtask_id]
            session = self._find_sessions(subtask_id)

            if session:
                self._send_failure(session, wtf)
            else:
                self.task_service.spawn_connect(
                    wtf.owner.key,
                    addresses=wtf.owner.get_addresses(),
                    cb=lambda session, w=wtf: self._send_failure(session, w),
                    eb=self.noop
                )

        # FIXME: Is this the right approach?
        self.failures_to_send.clear()

    def _send_failure(self, session, wtf):
        self.failures_to_send.pop(wtf.subtask_id, None)
        self.task_service.send_failure(session, wtf.subtask_id, wtf.err_msg)

    def _find_sessions(self, subtask_id):
        return self.task_sessions.get(subtask_id)

    @staticmethod
    def __get_task_manager_root(datadir):
        return os.path.join(datadir, "res")


class WaitingTaskResult(object):
    def __init__(self, task_id, subtask_id, computing_time,
                 resource_hash, resource_secret, resource_options,
                 owner, last_sending_trial=0, delay_time=0):

        self.task_id = task_id
        self.subtask_id = subtask_id
        self.computing_time = computing_time
        self.resource_hash = resource_hash
        self.resource_secret = resource_secret
        self.resource_options = resource_options
        self.owner = owner

        self.last_sending_trial = last_sending_trial
        self.delay_time = delay_time

        self.already_sending = False

    def can_send(self):
        return not self.already_sending and \
               time.time() - self.last_sending_trial > self.delay_time

    def mark_sending(self):
        self.already_sending = True
        self.last_sending_trial = time.time()

    def reset(self, delay_time):
        self.last_sending_trial = time.time()
        self.delay_time = delay_time
        self.already_sending = False


class WaitingTaskFailure(object):
    def __init__(self, task_id, subtask_id, err_msg, owner):

        self.task_id = task_id
        self.subtask_id = subtask_id
        self.owner = owner
        self.err_msg = err_msg


class TaskResultWrapper:

    def __init__(self, task_id, subtask_id, result, owner):

        self.task_id = task_id
        self.subtask_id = subtask_id
        self.result = result['data']
        self.result_type = result['result_type']
        self.owner = owner
        self.owner_key_id = owner.key
