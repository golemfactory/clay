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
    return reactor

############################
def registerGui(logic, app, gui):
    logic.registerGui(app.getMainWindow(), gui)

############################
def registerRenderingTaskTypes(logic):
    logic.registerNewRendererType(buildPBRTRendererInfo())
    logic.registerNewRendererType(build3dsMaxRendererInfo())
    logic.registerNewRendererType(buildVRayRendererInfo())
    logic.registerNewRendererType(buildLuxRenderInfo())
    logic.registerNewRendererType(buildBlenderRendererInfo())

############################
def registerTaskTypes(logic):
    logic.registerNewTaskType(buildPBRTTaskType())
    logic.registerNewTaskType(build3dsMaxTaskType())
    logic.registerNewTaskType(buildVRayTaskType())
    logic.registerNewTaskType(buildPythonGNRTaskType())
    logic.registerNewTaskType(buildLuxRenderTaskType())
    logic.registerNewTaskType(buildBlenderRenderTaskType())

############################
def loadEnvironments():

    return [PBRTEnvironment(),
            ThreeDSMaxEnvironment(),
            VRayEnvironment(),
            LuxRenderEnvironment(),
            BlenderEnvironment(),
            Environment() ]

############################
def startAndConfigureClient(logic, environments):
    client = startClient()
    for env in environments:
        client.environmentsManager.addEnvironment(env)

    client.environmentsManager.loadConfig(client.config_desc.client_uid)

    logic.registerClient(client)
    logic.checkNetworkState()

    return client

############################
def runManager(logic, client):
    path = os.getcwd()
    def runGNRNodes(numNodes):
        runAdditionalNodes(path, numNodes)

    nmPath = os.path.join(path, "..\\manager\\")
    def runGNRManager():
        runManager(nmPath)

    logic.registerStartNewNodeFunction(runGNRNodes)
    logic.registerStartNodesManagerFunction(runGNRManager)

    client.environmentsManager.loadConfig(client.config_desc.client_uid)

############################
def runInfoServer(client, start_port = 55555, nextPort = 55556, end_port = 59999):
    from examples.gnr.InfoServer import InfoServer
    infoServer = InfoServer(client, start_port, nextPort, end_port)
    infoServer.start()

############################
def runManagerClient(logic):
    logic.startNodesManagerClient()

############################
def runRanking(client, reactor):
    client.ranking.run(reactor)

############################
def runAddTaskClient(logic):
    logic.startAddTaskClient()

############################
def runAddTaskServer(client):
   client.runAddTaskServer()
 #   from PluginServer import TaskAdderServer
 #   server =  TaskAdderServer(client.getPluginPort())
 #   server.start()

###########################################################################
def startApp(logic, app, gui, rendering = False, startManager = False, startManagerClient = False, startInfoServer = False, startRanking = True, startAddTaskClient = False, startAddTaskServer = False ):
    reactor = install_reactor()
    registerGui(logic, app, gui)
    if rendering:
        registerRenderingTaskTypes(logic)
    else:
        registerTaskTypes(logic)
    environments = loadEnvironments()

    client = startAndConfigureClient(logic, environments)

    if startManager:
        runManager(logic, client)
    if startManagerClient:
        runManagerClient(logic)
    if startInfoServer:
        runInfoServer(client)
    if startRanking:
        runRanking(client, reactor)
    if startAddTaskClient:
        runAddTaskClient(logic)
    if startAddTaskServer:
        runAddTaskServer(client)

    app.execute(False)

    reactor.run()
