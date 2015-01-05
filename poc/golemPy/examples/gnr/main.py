import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from RenderingApplicationLogic import RenderingApplicationLogic


from golem.Client import startClient
from golem.environments.Environment import Environment

from examples.gnr.task.PbrtGNRTask import buildPBRTRendererInfo
from examples.gnr.task.ThreeDSMaxTask import build3dsMaxRendererInfo
from examples.gnr.task.VRayTask import buildVRayRendererInfo
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment
from examples.gnr.ui.MainWindow import RenderingMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingMainWindowCustomizer import RenderingMainWindowCustomizer


def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingApplicationLogic()
    app     = GNRGui( logic, RenderingMainWindow )

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.registerGui( app.getMainWindow(), RenderingMainWindowCustomizer )

    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( build3dsMaxRendererInfo() )
    logic.registerNewRendererType( buildVRayRendererInfo() )

    environments = [PBRTEnvironment(), ThreeDSMaxEnvironment(), VRayEnvironment(), Environment() ]

    client = startClient( )

    for env in environments:
        client.environmentsManager.addEnvironment( env )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

    logic.registerClient( client )
    logic.checkNetworkState()

    app.execute( False )

    reactor.run()

main()
