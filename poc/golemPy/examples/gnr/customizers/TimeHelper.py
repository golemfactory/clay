def __count_time(timeout):
    hours = timeout / 3600
    minutes = (timeout % 3600) / 60
    seconds = timeout % 60
    return hours, minutes, seconds


def set_time_spin_boxes(gui, full_task_timeout, subtask_timeout, min_subtask_time):
    hours, minutes, seconds = __count_time(full_task_timeout)
    gui.ui.fullTaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.fullTaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.fullTaskTimeoutSecSpinBox.setValue(seconds)
    hours, minutes, seconds = __count_time(subtask_timeout)
    gui.ui.subtaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.subtaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.subtaskTimeoutSecSpinBox.setValue(seconds)
    hours, minutes, seconds = __count_time(min_subtask_time)
    gui.ui.minSubtaskTimeHourSpinBox.setValue(hours)
    gui.ui.minSubtaskTimeMinSpinBox.setValue(minutes)
    gui.ui.minSubtaskTimeSecSpinBox.setValue(seconds)


def get_time_values(gui):
    full_task_timeout = gui.ui.fullTaskTimeoutHourSpinBox.value() * 3600
    full_task_timeout += gui.ui.fullTaskTimeoutMinSpinBox.value() * 60
    full_task_timeout += gui.ui.fullTaskTimeoutSecSpinBox.value()
    subtask_timeout = gui.ui.subtaskTimeoutHourSpinBox.value() * 3600
    subtask_timeout += gui.ui.subtaskTimeoutMinSpinBox.value() * 60
    subtask_timeout += gui.ui.subtaskTimeoutSecSpinBox.value()
    min_subtask_time = gui.ui.minSubtaskTimeHourSpinBox.value() * 3600
    min_subtask_time += gui.ui.minSubtaskTimeMinSpinBox.value() * 60
    min_subtask_time += gui.ui.minSubtaskTimeSecSpinBox.value()
    return full_task_timeout, subtask_timeout, min_subtask_time
