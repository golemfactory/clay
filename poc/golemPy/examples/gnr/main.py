import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from GNRApplicationLogic import GNRApplicationLogic

from Application import GNRGui
from golem.Client import startClient

from TaskState import RendererDefaults, RendererInfo, TestTaskInfo
from task.PbrtGNRTask import buildPBRTRendererInfo
from task.ThreeDSMaxTask import build3dsMaxRendererInfo
from task.VRayTask import buildVRayRendererInfo

from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment
from golem.environments.Environment import Environment

def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = GNRApplicationLogic()
    app     = GNRGui( logic )

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.registerGui( app.getMainWindow() )

    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( build3dsMaxRendererInfo() )
    logic.registerNewRendererType( buildVRayRendererInfo() )
    logic.registerNewTestTaskType( TestTaskInfo( "CornellBox" ) )

    environments = [PBRTEnvironment(), ThreeDSMaxEnvironment(), VRayEnvironment(), Environment() ]

    client = startClient( )

    for env in environments:
        client.environmentsManager.addEnvironment( env )
    logic.registerClient( client )
    logic.checkNetworkState()

    app.execute( False )

    reactor.run()

main()
