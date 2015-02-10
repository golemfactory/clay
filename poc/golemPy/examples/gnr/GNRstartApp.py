import os

from golem.Client import startClient
from golem.environments.Environment import Environment

from examples.gnr.RenderingEnvironment import ThreeDSMaxEnvironment, PBRTEnvironment, VRayEnvironment, LuxRenderEnvironment, BlenderEnvironment
from examples.gnr.TaskType import buildPBRTTaskType, build3dsMaxTaskType, buildVRayTaskType, buildPythonGNRTaskType, buildLuxRenderTaskType, buildBlenderRenderTaskType
from examples.gnr.task.PbrtGNRTask import buildPBRTRendererInfo
from examples.gnr.task.ThreeDSMaxTask import build3dsMaxRendererInfo
from examples.gnr.task.VRayTask import buildVRayRendererInfo
from examples.gnr.task.LuxRenderTask import buildLuxRenderInfo
from examples.gnr.task.BlenderRenderTask import buildBlenderRendererInfo

from examples.gnr.InfoServer import InfoServer

from examples.manager.GNRManagerLogic import runAdditionalNodes, runManager

###########################################################################
def install_reactor():
    try:
        import qt4reactor
    except ImportError:
        # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

############################
def registerGui( logic, app, gui ):
    logic.registerGui( app.getMainWindow(), gui )

############################
def registerRenderingTaskTypes( logic ):
    logic.registerNewRendererType( buildPBRTRendererInfo() )
    logic.registerNewRendererType( build3dsMaxRendererInfo() )
    logic.registerNewRendererType( buildVRayRendererInfo() )
    logic.registerNewRendererType( buildLuxRenderInfo() )
    logic.registerNewRendererType( buildBlenderRendererInfo() )

############################
def registerTaskTypes( logic ):
    logic.registerNewTaskType( buildPBRTTaskType() )
    logic.registerNewTaskType( build3dsMaxTaskType() )
    logic.registerNewTaskType( buildVRayTaskType() )
    logic.registerNewTaskType( buildPythonGNRTaskType() )
    logic.registerNewTaskType( buildLuxRenderTaskType() )
    logic.registerNewRendererType( buildBlenderRenderTaskType() )

############################
def loadEnvironments():

    return [PBRTEnvironment(),
            ThreeDSMaxEnvironment(),
            VRayEnvironment(),
            LuxRenderEnvironment(),
            BlenderEnvironment(),
            Environment() ]

############################
def startAndConfigureClient( logic, environments ):
    client = startClient()
    for env in environments:
        client.environmentsManager.addEnvironment( env )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

    logic.registerClient( client )
    logic.checkNetworkState()

    return client

############################
def runManager( logic, client):
    path = os.getcwd()
    def runGNRNodes( numNodes ):
        runAdditionalNodes( path, numNodes )

    nmPath = os.path.join(path, "..\\manager\\" )
    def runGNRManager( ):
        runManager( nmPath )

    logic.registerStartNewNodeFunction( runGNRNodes )
    logic.registerStartNodesManagerFunction( runGNRManager )

    client.environmentsManager.loadConfig( client.configDesc.clientUid )

############################
def runInfoServer( client, startPort = 55555, nextPort = 55556, endPort = 59999 ):
    infoServer = InfoServer( client, startPort, nextPort, endPort )
    infoServer.start()

############################
def runManagerClient( logic ):
    logic.startNodesManagerClient()

###########################################################################
def startRenderingApp( logic, app, gui, startManager = False, startManagerClient = False, startInfoServer = False ):
    install_reactor()
    registerGui( logic, app, gui )
    registerRenderingTaskTypes( logic )
    environments = loadEnvironments()

    client = startAndConfigureClient( logic, environments )

    if startManager:
        runManager( logic, client )
    if startManagerClient:
        runManagerClient( logic )
    if startInfoServer:
        runInfoServer( client )

    app.execute( False )

    reactor.run()

###########################################################################
def startGNRApp( logic, app, gui, startManager = False, startManagerClient = False, startInfoServer = False ):
    install_reactor()
    registerGui( logic, app, gui )
    registerTaskTypes( logic )
    environments = loadEnvironments()

    client = startAndConfigureClient( logic, environments )

    if startManager:
        runManager( logic, client )
    if startManagerClient:
        runManagerClient( logic )
    if startInfoServer:
        runInfoServer( client )

    app.execute( False )
    reactor.run()