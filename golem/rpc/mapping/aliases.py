class Environment(object):

    opts                    = 'env.opts'
    opts_update             = 'env.opts.update'
    opt                     = 'env.opt'
    opt_update              = 'env.opt.update'

    # FIXME: description is saved in DB, not config file
    opt_description         = 'env.opt.description'
    opt_description_update  = 'env.opt.description.update'
    # FIXME: refactor
    use_ranking             = 'env.use_ranking'
    use_transaction_system  = 'env.use_transaction_system'

    datadir                 = 'env.datadir'

    evt_opts_changed        = 'evt.env.opts'


class Crypto(object):

    key_id                  = 'crypto.keys.id'
    pub_key                 = 'crypto.keys.pub'
    difficulty              = 'crypto.difficulty'


class Network(object):

    ident                   = 'net.ident'
    ident_key               = 'net.ident.key'
    status                  = 'net.status'

    peers_known             = 'net.peers.known'
    peers_connected         = 'net.peers.connected'

    peer                    = 'net.peer'
    peer_connect            = 'net.peer.connect'
    peer_disconnect         = 'net.peer.disconnect'

    supernodes              = 'net.supernodes'
    supernode               = 'net.supernode'
    supernode_create        = 'net.supernode.create'
    supernode_delete        = 'net.supernode.delete'

    p2p_port                = 'net.p2p.port'
    tasks_port              = 'net.tasks.port'

    evt_peer_connected      = 'evt.net.peer.connected'
    evt_peer_disconnected   = 'evt.net.peer.disconnected'
    evt_connection          = 'evt.net.connection'


class Reputation(object):

    computing               = 'rep.comp'
    requesting              = 'rep.requesting'
    evt_peer                = 'evt.rep.peer'


class Task(object):

    tasks                   = 'comp.tasks'
    tasks_check             = 'comp.tasks.check'
    tasks_check_abort       = 'comp.tasks.check.abort'
    tasks_stats             = 'comp.tasks.stats'
    tasks_known             = 'comp.tasks.known'
    tasks_known_delete      = 'comp.tasks.known.delete'

    task                    = 'comp.task'
    task_cost               = 'comp.task.cost'
    task_state              = 'comp.task.state'
    task_create             = 'comp.task.create'
    task_delete             = 'comp.task.delete'
    task_abort              = 'comp.task.abort'
    task_restart            = 'comp.task.restart'
    task_pause              = 'comp.task.pause'
    task_resume             = 'comp.task.resume'
    # task_price              = 'comp.task.price'
    # task_price_update       = 'comp.task.price.update'

    subtasks                = 'comp.task.subtasks'
    subtask                 = 'comp.task.subtask'
    subtask_restart         = 'comp.task.subtask.restart'

    evt_task_status         = 'evt.comp.task.status'
    evt_subtask_status      = 'evt.comp.subtask.status'

    evt_task_check_started  = 'evt.comp.task.check.started'
    evt_task_check_success  = 'evt.comp.task.check.success'
    evt_task_check_error    = 'evt.comp.task.check.error'


class Resources(object):

    directories             = 'res.dirs'
    directories_size        = 'res.dirs.size'
    directory               = 'res.dir'

    clear_directory         = 'res.dir.clear'

    evt_limit_exceeded      = 'evt.res.limit.exceeded'


class Computation(object):

    status                  = 'comp.status'
    environments            = 'comp.environments'
    environments_perf       = 'comp.environments.perf'
    enable_environment      = 'comp.environment.enable'
    disable_environment     = 'comp.environment.disable'
    benchmark_environment   = 'comp.environment.benchmark'

    evt_comp_started        = 'comp.started'
    evt_comp_finished       = 'comp.finished'


class Payments(object):

    ident                   = 'pay.ident'
    balance                 = 'pay.balance'

    payments                = 'pay.payments'
    payment                 = 'pay.payment'

    incomes                 = 'pay.incomes'
    income                  = 'pay.income'

    evt_payment             = 'evt.pay.payment'
    evt_income              = 'evt.pay.income'


class UI(object):

    quit                    = 'ui.quit'

    evt_lock_config         = 'evt.ui.widget.config.lock'


class Applications(object):
    # 'app'
    pass


NAMESPACES = [
    Environment,
    Crypto,
    Network,
    Reputation,
    Resources,
    Computation,
    Applications,
    UI,
]

