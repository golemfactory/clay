from golem.rpc.mapping.rpceventnames import *

GUI_EVENT_MAP = dict(
    config_changed=                 Environment.evt_opts_changed,

    task_status_changed=            Task.evt_task_status,

    connection_status_changed=      Network.evt_connection,

    lock_config=                    UI.evt_lock_config,
)
