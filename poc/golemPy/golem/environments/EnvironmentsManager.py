class EnvironmentsManager:
    def __init__( self ):
        self.supportedEnvironments = set()
        self.environments = set()

    def addEnvironment( self, environment ):
        self.environments.add( environment )
        if environment.supported():
            self.supportedEnvironments.add( environment.getId() )

    def supported( self, envId ):
        return envId in self.supportedEnvironments

