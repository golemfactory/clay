from golem.task.TaskBase import ( Task,
                                TaskHeader )

class GNRTask( Task ):
    # ####################
    def __init__( self, srcCode, clientId, taskId, ownerAddress, ownerPort, ttl, subtaskTtl, resourceSize ):
        Task.__init__( self, TaskHeader( clientId, taskId, ownerAddress, ownerPort, ttl, subtaskTtl, resourceSize ), srcCode )

    # ####################
    def getPreviewFilePath( self ):
        return None


