import zerorpc

c = zerorpc.Client()
c.connect("tcp://127.0.0.1:55555")

output = c.send_snapshot()