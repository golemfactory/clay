import sys
import os
import logging
import logging.config

sys.path.append( os.environ.get( 'GOLEM' ) )

from tools.UiGen import genUiFiles
genUiFiles( "ui" )

from RenderingAdmApplicationLogic import RenderingAdmApplicationLogic


from golem.Client import startClient
from golem.environments.Environment import Environment

from examples.gnr.task.PbrtGNRTask import buildPBRTRendererInfo
from examples.gnr.task.ThreeDSMaxTask import build3dsMaxRendererInfo
from examples.gnr.task.VRayTask import buildVRayRendererInfo
from examples.gnr.task.LuxRenderTask import buildLuxRenderInfo
from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment, LuxRenderEnvironment
from examples.gnr.ui.AdministrationMainWindow import AdministrationMainWindow
from examples.gnr.Application import GNRGui
from examples.gnr.customizers.RenderingAdmMainWindowCustomizer import RenderingAdmMainWindowCustomizer


def main():

    logging.config.fileConfig('logging.ini', disable_existing_loggers=False)

    logic   = RenderingAdmApplicationLogic()
    app     = GNRGui( logic, AdministrationMainWindow )

    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    logic.registerGui( app.getMainWindow(), RenderingAdmMainWindowCustomizer )

    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( build3dsMaxRendererInfo() )
    logic.registerNewRendererType( buildVRayRendererInfo() )
    logic.registerNewRendererType( buildLuxRenderInfo() )

    environments = [PBRTEnvironment(), ThreeDSMaxEnvironment(), VRayEnvironment(), LuxRenderEnvironment(), Environment() ]

    client = startClient( )

    for env in environments:
        client.environmentsManager.addEnvironment( env )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

    logic.registerClient( client )
    logic.checkNetworkState()

    app.execute( False )

    reactor.run()

main()
