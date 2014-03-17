from twisted.web import server, resource
from twisted.internet import reactor

class HelloResource(resource.Resource):
    isLeaf = True
    numberRequests = 0
    
    def render_GET(self, request):
        self.numberRequests += 1
        request.setHeader("content-type", "text/plain")
        return "I am request #" + str(self.numberRequests) + "\n"

hr1 = HelloResource()
hr2 = HelloResource()
reactor.callInThread(reactor.listenTCP, 8080, server.Site(hr1))
reactor.callInThread(reactor.listenTCP, 8081, server.Site(hr2))
#reactor.listenTCP(8080, server.Site(hr1))
reactor.run()
