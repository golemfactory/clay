import sys
sys.path.append('../../')

from tools.UiGen import genUiFiles
genUiFiles( "./../../golem/ui" )

from golem.AppConfig import AppConfig
from golem.manager.NodesManager import  NodesManager
from GNRManagerLogic import GNRManagerLogic
from golem.Message import initManagerMessages
import logging.config


def main():

    logging.config.fileConfig('../gnr/logging.ini', disable_existing_loggers=False)
    initManagerMessages()

    try:
         import qt4reactor
    except ImportError:
         # Maybe qt4reactor is placed inside twisted.internet in site-packages?
        from twisted.internet import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor

    port = AppConfig.managerPort()
    manager = NodesManager( None )
    logic = GNRManagerLogic(  manager.managerServer )
    manager.setManagerLogic( logic )


    logic.setReactor( reactor )
    manager.execute( True )

    reactor.run()
    sys.exit( 0 )

main()
