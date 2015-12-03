from testtasks.execution_time_measure import measure

def blender_performance():
    '''
    returns time (in seconds) needed to render the example scene
    '''
    return measure(["blender","-b","blender_task/scene-Helicopter-27.blend","-F","JPEG","-x","1","-f","1"])