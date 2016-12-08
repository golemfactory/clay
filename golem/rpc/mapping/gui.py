from golem.rpc.mapping.aliases import *

GUI_EVENT_MAP = dict(
    config_changed=                 Environment.evt_opts_changed,

    test_task_started=              Task.evt_task_check_started,
    test_task_computation_success=  Task.evt_task_check_success,
    test_task_computation_error=    Task.evt_task_check_error,

    task_status_changed=            Task.evt_task_status,

    connection_status_changed=      Network.evt_connection,

    lock_config=                    UI.evt_lock_config,
)
