from testtasks.execution_time_measure import measure

def lux_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    return measure(["luxconsole", "lux_task/scene-Helicopter-27.Scene.00001.lxs"])