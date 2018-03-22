# pylint: disable=bad-whitespace
# flake8: noqa

CORE_METHOD_MAP = dict(
    get_golem_version=      'golem.version',
    get_golem_status=       'golem.status',

    get_settings=           'env.opts',
    update_settings=        'env.opts.update',
    get_setting=            'env.opt',
    update_setting=         'env.opt.update',
    get_datadir=            'env.datadir',

    get_hw_caps=            'env.hw.caps',
    get_hw_presets=         'env.hw.presets',
    get_hw_preset=          'env.hw.preset',
    create_hw_preset=       'env.hw.preset.create',
    update_hw_preset=       'env.hw.preset.update',
    delete_hw_preset=       'env.hw.preset.delete',
    activate_hw_preset=     'env.hw.preset.activate',

    use_ranking=            'env.use_ranking',

    get_key_id=             'crypto.keys.id',
    get_public_key=         'crypto.keys.pub',
    get_difficulty=         'crypto.difficulty',

    get_node=               'net.ident',
    get_node_key=           'net.ident.key',
    get_node_name=          'net.ident.name',
    get_known_peers=        'net.peers.known',
    get_connected_peers=    'net.peers.connected',

    connect=                'net.peer.connect',
    connection_status=      'net.status',

    get_p2p_port=           'net.p2p.port',
    get_task_server_port=   'net.tasks.port',

    get_computing_trust=    'rep.comp',
    get_requesting_trust=   'rep.requesting',

    get_tasks=              'comp.tasks',
    get_task=               'comp.task',
    run_test_task=          'comp.tasks.check',
    check_test_status=      'comp.task.test.status',
    abort_test_task=        'comp.tasks.check.abort',
    get_unsupport_reasons=  'comp.tasks.unsupport',
    get_task_stats=         'comp.tasks.stats',
    get_known_tasks=        'comp.tasks.known',
    remove_task_header=     'comp.tasks.known.delete',
    save_task_preset=       'comp.tasks.preset.save',
    get_task_presets=       'comp.tasks.preset.get',
    delete_task_preset=     'comp.tasks.preset.delete',
    get_estimated_cost=     'comp.tasks.estimated.cost',

    get_task_cost=          'comp.task.cost',
    get_task_preview=       'comp.task.preview',
    query_task_state=       'comp.task.state',
    create_task=            'comp.task.create',
    delete_task=            'comp.task.delete',
    abort_task=             'comp.task.abort',
    restart_task=           'comp.task.restart',

    get_subtasks=           'comp.task.subtasks',
    get_subtasks_borders=   'comp.task.subtasks.borders',
    get_subtasks_frames=    'comp.task.subtasks.frames',
    get_subtask=            'comp.task.subtask',
    restart_subtask=        'comp.task.subtask.restart',
    restart_frame_subtasks= 'comp.task.subtasks.frame.restart',

    get_res_dirs=           'res.dirs',
    get_res_dir=            'res.dir',
    get_res_dirs_sizes=     'res.dirs.size',
    clear_dir=              'res.dir.clear',

    get_status=             'comp.status',
    get_environments=       'comp.environments',
    enable_environment=     'comp.environment.enable',
    disable_environment=    'comp.environment.disable',
    run_benchmark=          'comp.environment.benchmark',
    get_performance_values= 'comp.environment.performance',

    get_payment_address=    'pay.ident',
    get_balance=            'pay.balance',
    get_payments_list=      'pay.payments',
    get_incomes_list=       'pay.incomes',
    withdraw=               'pay.withdraw',

    quit=                   'ui.quit',
    resume=                 'ui.start',
    pause=                  'ui.stop'
)

NODE_METHOD_MAP = dict(
    set_password=           'golem.password.set',
    key_exists=             'golem.password.key_exists',
    is_mainnet=             'golem.mainnet',
    are_terms_accepted=     'golem.terms',
    accept_terms=           'golem.terms.accept',
    show_terms=             'golme.terms.show',
)
