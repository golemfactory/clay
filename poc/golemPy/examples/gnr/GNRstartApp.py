from golem.environments.Environment import Environment

from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment, LuxRenderEnvironment
from examples.gnr.task.PbrtGNRTask import buildPBRTRendererInfo
from examples.gnr.task.ThreeDSMaxTask import build3dsMaxRendererInfo
from examples.gnr.task.VRayTask import buildVRayRendererInfo
from examples.gnr.task.LuxRenderTask import buildLuxRenderInfo

from golem.Client import startClient

def install_reactor():
    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

def registerGui( logic, app, gui ):
    logic.registerGui( app.getMainWindow(), gui )

def registerTaskTypes( logic ):
    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( build3dsMaxRendererInfo() )
    logic.registerNewRendererType( buildVRayRendererInfo() )
    logic.registerNewRendererType( buildLuxRenderInfo() )
  #  logic.registerNewRendererType( buildBlenderRenderInfo() )

def startAndConfigureClient( logic, environments ):
    client = startClient()
    for env in environments:
        client.environmentsManager.addEnvironment( env )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

    logic.registerClient( client )
    logic.checkNetworkState()

    return client

def startApp( logic, app, gui ):
    install_reactor()
    registerGui( logic, app, gui )
    registerTaskTypes( logic )

    environments = [PBRTEnvironment(),
                    ThreeDSMaxEnvironment(),
                    VRayEnvironment(),
                    LuxRenderEnvironment(),
                    Environment() ]

    client = startAndConfigureClient( logic, environments )

    app.execute( False )

    reactor.run()