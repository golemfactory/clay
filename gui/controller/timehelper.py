def __count_time(timeout):
    hours = timeout / 3600
    minutes = (timeout % 3600) / 60
    seconds = timeout % 60
    return hours, minutes, seconds


def set_time_spin_boxes(gui, full_task_timeout, subtask_timeout):
    hours, minutes, seconds = __count_time(full_task_timeout)
    gui.ui.fullTaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.fullTaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.fullTaskTimeoutSecSpinBox.setValue(seconds)
    hours, minutes, seconds = __count_time(subtask_timeout)
    gui.ui.subtaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.subtaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.subtaskTimeoutSecSpinBox.setValue(seconds)


def get_time_values(gui):
    full_task_timeout = gui.ui.fullTaskTimeoutHourSpinBox.value() * 3600
    full_task_timeout += gui.ui.fullTaskTimeoutMinSpinBox.value() * 60
    full_task_timeout += gui.ui.fullTaskTimeoutSecSpinBox.value()
    subtask_timeout = gui.ui.subtaskTimeoutHourSpinBox.value() * 3600
    subtask_timeout += gui.ui.subtaskTimeoutMinSpinBox.value() * 60
    subtask_timeout += gui.ui.subtaskTimeoutSecSpinBox.value()
    return full_task_timeout, subtask_timeout


def get_subtask_hours(gui):
    """ Get subtask timeout in hours
    :param gui: dialog customizer containing subtaskTimeoutHourSpinBoxes
    :return float: subtask timeout in hours
    """
    return gui.ui.subtaskTimeoutHourSpinBox.value() + gui.ui.subtaskTimeoutMinSpinBox.value() / 60.0 + \
           gui.ui.subtaskTimeoutSecSpinBox.value() / 3600.0
