# Golem
The aim of the Golem project is to create a global prosumer market for computing power, in which
producers may sell spare CPU time of their personal computers and consumers may acquire resources
for computation-intensive tasks. In technical terms, Golem is designed as a decentralised peer-to-peer
network established by nodes running the Golem client software. For the purpose of this paper we assume
that there are two types of nodes in the Golem network: requester nodes that announce computing
tasks and compute nodes that perform computations (in the actual implementation nodes may switch
between both roles).

1) Set environment variable "GOLEM" to "<path_to_golem>/golem/poc/golemPy"

2) Run pip install -r requirements.txt

3) Download: http://excamera.com/files/OpenEXR-1.2.0.tar.gz, extract and run

sudo python setup.py install

4) Install PyQt4 by following the instruction from: http://pyqt.sourceforge.net/Docs/PyQt4/installation.html
5) Set envrionment variable QT_GRAPHICSSYSTEM=native

5) To start application go to poc/golemPy/examples/gnr and run admMain.py.


