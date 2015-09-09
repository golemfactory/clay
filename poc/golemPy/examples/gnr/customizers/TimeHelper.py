def __countTime(timeout):
        hours = timeout / 3600
        minutes = (timeout % 3600) / 60
        seconds = timeout % 60
        return hours, minutes, seconds

def setTimeSpinBoxes(gui, full_task_timeout, subtask_timeout, min_subtask_time):
    hours, minutes, seconds = __countTime(full_task_timeout)
    gui.ui.fullTaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.fullTaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.fullTaskTimeoutSecSpinBox.setValue(seconds)
    hours, minutes, seconds = __countTime(subtask_timeout)
    gui.ui.subtaskTimeoutHourSpinBox.setValue(hours)
    gui.ui.subtaskTimeoutMinSpinBox.setValue(minutes)
    gui.ui.subtaskTimeoutSecSpinBox.setValue(seconds)
    hours, minutes, seconds = __countTime(min_subtask_time)
    gui.ui.minSubtaskTimeHourSpinBox.setValue(hours)
    gui.ui.minSubtaskTimeMinSpinBox.setValue(minutes)
    gui.ui.minSubtaskTimeSecSpinBox.setValue(seconds)

def getTimeValues(gui):
    full_task_timeout   = gui.ui.fullTaskTimeoutHourSpinBox.value() * 3600 + gui.ui.fullTaskTimeoutMinSpinBox.value() * 60 + gui.ui.fullTaskTimeoutSecSpinBox.value()
    subtask_timeout   = gui.ui.subtaskTimeoutHourSpinBox.value() * 3600 + gui.ui.subtaskTimeoutMinSpinBox.value() * 60 + gui.ui.subtaskTimeoutSecSpinBox.value()
    min_subtask_time   = gui.ui.minSubtaskTimeHourSpinBox.value() * 3600 + gui.ui.minSubtaskTimeMinSpinBox.value() * 60 + gui.ui.minSubtaskTimeSecSpinBox.value()
    return full_task_timeout, subtask_timeout, min_subtask_time