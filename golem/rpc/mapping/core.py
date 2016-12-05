from golem.rpc.mapping.aliases import *

CORE_METHOD_MAP = dict(
    get_config=             Environment.opts,
    get_setting=            Environment.opt,
    update_setting=         Environment.opt_update,
    get_datadir=            Environment.datadir,
    get_description=        Environment.opt_description,

    get_key_id=             Crypto.key_id,
    get_public_key=         Crypto.pub_key,
    get_difficulty=         Crypto.difficulty,

    get_node=               Network.ident,
    get_node_key=           Network.ident_key,
    get_known_peers=        Network.peers_known,
    get_connected_peers=    Network.peers_connected,

    connect=                Network.peer_connect,

    get_p2p_port=           Network.p2p_port,
    get_task_server_port=   Network.tasks_port,

    get_computing_trust=    Reputation.computing,
    get_requesting_trust=   Reputation.requesting,

    get_tasks=              Task.tasks,
    run_test_task=          Task.tasks_check,
    get_task_stats=         Task.tasks_stats,
    get_known_tasks=        Task.tasks_known,
    remove_task_header=     Task.tasks_known_delete,

    get_task=               Task.task,
    enqueue_new_task=       Task.task_create,
    remove_task=            Task.task_delete,
    abort_task=             Task.task_abort,
    restart_task=           Task.task_restart,
    pause_task=             Task.task_pause,
    resume_task=            Task.task_resume,

    get_subtasks=           Task.subtasks,
    get_subtask=            Task.subtask,
    restart_subtask=        Task.subtask_restart,

    get_res_dirs=           Resources.dirs,
    get_res_dirs_sizes=     Resources.dir_sizes,

    get_status=             Computation.status,
    get_environments=       Computation.environments,

    get_payment_address=    Payments.ident,
    get_payments_list=      Payments.payments,
    get_incomes_list=       Payments.incomes,

    quit=                   UI.quit
)

