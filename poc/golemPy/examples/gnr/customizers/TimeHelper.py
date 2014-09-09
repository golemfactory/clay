def __countTime( timeout ):
        hours = timeout / 3600
        minutes = (timeout % 3600) / 60
        seconds = timeout % 60
        return hours, minutes, seconds

def setTimeSpinBoxes( gui, fullTaskTimeout, subtaskTimeout, minSubtaskTime ):
    hours, minutes, seconds = __countTime( fullTaskTimeout )
    gui.ui.fullTaskTimeoutHourSpinBox.setValue( hours )
    gui.ui.fullTaskTimeoutMinSpinBox.setValue( minutes )
    gui.ui.fullTaskTimeoutSecSpinBox.setValue( seconds )
    hours, minutes, seconds = __countTime( subtaskTimeout )
    gui.ui.subtaskTimeoutHourSpinBox.setValue( hours )
    gui.ui.subtaskTimeoutMinSpinBox.setValue( minutes )
    gui.ui.subtaskTimeoutSecSpinBox.setValue( seconds )
    hours, minutes, seconds = __countTime( minSubtaskTime )
    gui.ui.minSubtaskTimeHourSpinBox.setValue( hours )
    gui.ui.minSubtaskTimeMinSpinBox.setValue( minutes )
    gui.ui.minSubtaskTimeSecSpinBox.setValue( seconds )

def getTimeValues(gui):
    fullTaskTimeout   = gui.ui.fullTaskTimeoutHourSpinBox.value() * 3600 + gui.ui.fullTaskTimeoutMinSpinBox.value() * 60 + gui.ui.fullTaskTimeoutSecSpinBox.value()
    subtaskTimeout   = gui.ui.subtaskTimeoutHourSpinBox.value() * 3600 + gui.ui.subtaskTimeoutMinSpinBox.value() * 60 + gui.ui.subtaskTimeoutSecSpinBox.value()
    minSubtaskTime   = gui.ui.minSubtaskTimeHourSpinBox.value() * 3600 + gui.ui.minSubtaskTimeMinSpinBox.value() * 60 + gui.ui.minSubtaskTimeSecSpinBox.value()
    return fullTaskTimeout, subtaskTimeout, minSubtaskTime