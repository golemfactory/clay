from golem.rpc.mapping.aliases import *

GUI_EVENT_MAP = dict(
    test_task_started=              Task.evt_task_check_started,
    test_task_computation_success=  Task.evt_task_check_success,
    test_task_computation_error=    Task.evt_task_check_error
)
