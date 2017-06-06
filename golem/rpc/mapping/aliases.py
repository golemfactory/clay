class Environment(object):

    opts                    = 'env.opts'
    opts_update             = 'env.opts.update'
    opt                     = 'env.opt'
    opt_update              = 'env.opt.update'

    hardware_caps           = 'env.hw.caps'
    presets                 = 'env.hw.presets'
    preset                  = 'env.hw.preset'
    preset_create           = 'env.hw.preset.create'
    preset_activate         = 'env.hw.preset.activate'
    preset_update           = 'env.hw.preset.update'
    preset_delete           = 'env.hw.preset.delete'

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
    ident_name              = 'net.ident.name'
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
    tasks_save_preset       = 'comp.tasks.preset.save'
    tasks_load_presets      = 'comp.tasks.preset.get'
    tasks_remove_preset     = 'comp.tasks.preset.delete'

    task                    = 'comp.task'
    task_cost               = 'comp.task.cost'
    task_preview            = 'comp.task.preview'
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
    subtasks_borders        = 'comp.task.subtasks.borders'
    subtask                 = 'comp.task.subtask'
    subtask_restart         = 'comp.task.subtask.restart'

    evt_task_list           = 'evt.comp.task.list'
    evt_task_status         = 'evt.comp.task.status'
    evt_subtask_status      = 'evt.comp.subtask.status'
    evt_task_test_status    = 'evt.comp.task.test.status'


class Resources(object):

    directories             = 'res.dirs'
    directories_size        = 'res.dirs.size'
    directory               = 'res.dir'

    clear_directory         = 'res.dir.clear'

    evt_limit_exceeded      = 'evt.res.limit.exceeded'


class Computation(object):

    status                  = 'comp.status'
    environments            = 'comp.environments'
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

    evt_balance             = 'evt.pay.balance'
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

