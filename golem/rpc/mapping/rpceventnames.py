class Golem:
    evt_golem_status        = 'evt.golem.status'


class Environment:

    evt_opts_changed        = 'evt.env.opts'


class Network:

    peer                    = 'net.peer'
    peer_disconnect         = 'net.peer.disconnect'

    evt_peer_connected      = 'evt.net.peer.connected'
    evt_peer_disconnected   = 'evt.net.peer.disconnected'
    evt_connection          = 'evt.net.connection'


class Reputation:

    evt_peer                = 'evt.rep.peer'


class Task:

    evt_task_list           = 'evt.comp.task.list'
    evt_task_status         = 'evt.comp.task.status'
    evt_subtask_status      = 'evt.comp.subtask.status'
    evt_task_test_status    = 'evt.comp.task.test.status'


class Resources:

    evt_limit_exceeded      = 'evt.res.limit.exceeded'


class Computation:

    evt_comp_started        = 'comp.started'
    evt_comp_finished       = 'comp.finished'


class Payments:

    evt_balance             = 'evt.pay.balance'
    evt_payment             = 'evt.pay.payment'
    evt_income              = 'evt.pay.income'


class UI:

    evt_lock_config         = 'evt.ui.widget.config.lock'


NAMESPACES = [
    Golem,
    Environment,
    Network,
    Reputation,
    Task,
    Resources,
    Computation,
    Payments,
    UI,
]
