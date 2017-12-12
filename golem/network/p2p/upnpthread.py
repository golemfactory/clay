import copy
import logging
import os
import threading
import miniupnpc
from threading import Thread, Lock


logger = logging.getLogger("golem.task.upnpthread")


class UpnpThread(Thread):
    def __init__(self, ports, cleanup=False, retries=3):
        super(UpnpThread, self).__init__()

        self.ports = ports
        self.cleanup = cleanup
        self.retries = retries

        self._parent_thread = threading.current_thread()

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
        except Exception as exc:
            logger.exception("__do_work failed")

    def check_if_mapped(self, upnpc, port):
        redirect = upnpc.getspecificportmapping(port, 'TCP')
        if redirect is None:
            return False
        return True

    def __do_work(self):
        upnpc = miniupnpc.UPnP()
        upnpc.discoverdelay = 200
        devices = upnpc.discover()
        logger.debug("%d UPNP device(s) found", devices)
    
        if not devices:
            return
    
        upnpc.selectigd()
        external_ip = upnpc.externalipaddress()
        logger.debug("device external ip: %s", external_ip)

        if self.cleanup:
            for port in self.ports:
                retries = 0
                while True:
                    logger.debug("removing %s port %u TCP => %s port %u TCP", 
                    upnpc.lanaddr, port, external_ip, port)
                    if not self.check_if_mapped(upnpc, port):
                        logger.debug("%s port %u TCP does not exists", 
                        external_ip, port)
                        break

                    try:
                        res = upnpc.deleteportmapping(port, 'TCP')
                    except Exception as exc:
                        pass

                    if res:
                        logger.debug("Deleted with success")
                        break

                    retries = retries + 1
                    if self.retries > 0 and retries == self.retries:
                        break
        else:
            for port in self.ports:
                retries = 0
                while True:
                    logger.debug("redirecting %s port %u TCP => %s port %u TCP",
                    upnpc.lanaddr, port, external_ip, port)
                    if self.check_if_mapped(upnpc, port):
                        logger.debug("%s port %u TCP already redirected", external_ip, port)
                        break

                    res = upnpc.addportmapping(port, 'TCP', upnpc.lanaddr, port,
                    'golem port %u' % port, '')
                
                    if res:
                        logger.info("Redirected with success")
                        break

                    retries = retries + 1
                    if self.retries > 0 and retries == self.retries:
                        break
