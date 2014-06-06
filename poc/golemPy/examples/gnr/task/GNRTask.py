from src.task.TaskBase import ( Task,
                                TaskHeader )

class GNRTask( Task ):
    # ####################
    def __init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, ttl ):
        Task.__init__( TaskHeader( clientId, taskId, ownerAddress, ownerPort, ttl ), srcCode )


