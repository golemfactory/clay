from golem.rpc.mapping.aliases import *

CORE_METHOD_MAP = dict(
    get_settings=           Environment.opts,
    update_settings=        Environment.opts_update,
    get_setting=            Environment.opt,
    update_setting=         Environment.opt_update,
    get_datadir=            Environment.datadir,
    get_description=        Environment.opt_description,
    change_description=     Environment.opt_description_update,

    get_hw_caps=            Environment.hardware_caps,
    get_hw_presets=         Environment.presets,
    get_hw_preset=          Environment.preset,
    create_hw_preset=       Environment.preset_create,
    update_hw_preset=       Environment.preset_update,
    remove_hw_preset=       Environment.preset_delete,
    activate_hw_preset=     Environment.preset_activate,

    use_ranking=            Environment.use_ranking,
    use_transaction_system= Environment.use_transaction_system,

    get_key_id=             Crypto.key_id,
    get_public_key=         Crypto.pub_key,
    get_difficulty=         Crypto.difficulty,

    get_node=               Network.ident,
    get_node_key=           Network.ident_key,
    get_node_name=          Network.ident_name,
    get_known_peers=        Network.peers_known,
    get_connected_peers=    Network.peers_connected,

    connect=                Network.peer_connect,
    connection_status=      Network.status,

    get_p2p_port=           Network.p2p_port,
    get_task_server_port=   Network.tasks_port,

    get_computing_trust=    Reputation.computing,
    get_requesting_trust=   Reputation.requesting,

    get_tasks=              Task.tasks,
    run_test_task=          Task.tasks_check,
    abort_test_task=        Task.tasks_check_abort,
    get_task_stats=         Task.tasks_stats,
    get_known_tasks=        Task.tasks_known,
    remove_task_header=     Task.tasks_known_delete,
    save_task_preset=       Task.tasks_save_preset,
    load_task_presets=       Task.tasks_load_presets,

    get_task=               Task.task,
    get_task_cost=          Task.task_cost,
    query_task_state=       Task.task_state,
    create_task=            Task.task_create,
    delete_task=            Task.task_delete,
    abort_task=             Task.task_abort,
    restart_task=           Task.task_restart,
    pause_task=             Task.task_pause,
    resume_task=            Task.task_resume,

    get_subtasks=           Task.subtasks,
    get_subtask=            Task.subtask,
    restart_subtask=        Task.subtask_restart,

    get_res_dirs=           Resources.directories,
    get_res_dir=            Resources.directory,
    get_res_dirs_sizes=     Resources.directories_size,
    clear_dir=              Resources.clear_directory,

    get_status=             Computation.status,
    get_environments=       Computation.environments,
    enable_environment=     Computation.enable_environment,
    disable_environment=    Computation.disable_environment,
    run_benchmark=          Computation.benchmark_environment,

    get_payment_address=    Payments.ident,
    get_balance=            Payments.balance,
    get_payments_list=      Payments.payments,
    get_incomes_list=       Payments.incomes,

    quit=                   UI.quit
)

