import logging
import logging.config
import os
import sys

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from golem.network.transport.reactor import importReactor
from golem.environments.Environment import Environment
from golem.Client import startClient

from examples.gnr.GNRApplicationLogic import GNRApplicationLogic
from examples.gnr.Application import GNRGui
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment
from examples.gnr.InfoServer import InfoServer

from examples.manager.GNRManagerLogic import runAdditionalNodes, runManager

from examples.default.TaskType import buildPBRTTaskType, build3dsMaxTaskType, buildVRayTaskType, buildPythonGNRTaskType
from examples.default.ui.MainWindow import GNRMainWindow


def main():
    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic = GNRApplicationLogic()
    app     = GNRGui( logic, GNRMainWindow )

    logic.registerGui( app.getMainWindow() )

    logic.registerNewTaskType( buildPBRTTaskType() )

    logic.registerNewTaskType( build3dsMaxTaskType() )
    logic.registerNewTaskType( buildVRayTaskType() )
    logic.registerNewTaskType( buildPythonGNRTaskType() )

    importReactor()

    client = startClient()

    path = os.getcwd()
    def runGNRNodes( numNodes ):
        runAdditionalNodes( path, numNodes )

    nmPath = os.path.join(path, "..\\manager\\" )
    def runGNRManager( ):
        runManager( nmPath )

    logic.registerStartNewNodeFunction( runGNRNodes )
    logic.registerStartNodesManagerFunction( runGNRManager )

    environments = [PBRTEnvironment(), ThreeDSMaxEnvironment(), VRayEnvironment(), Environment() ]
    for env in environments:
        client.environmentsManager.addEnvironment( env )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

    logic.registerClient( client )
    logic.checkNetworkState()

    #logic.startNodesManagerClient()
    infoServer = InfoServer( client, 55555, 55556, 59999 )
    infoServer.start()

    app.execute( False )
    reactor.run()



main()