# Golem
The aim of the Golem project is to create a global prosumer market for computing power, in which
producers may sell spare CPU time of their personal computers and consumers may acquire resources
for computation-intensive tasks. In technical terms, Golem is designed as a decentralised peer-to-peer
network established by nodes running the Golem client software. For the purpose of this paper we assume
that there are two types of nodes in the Golem network: requester nodes that announce computing
tasks and compute nodes that perform computations (in the actual implementation nodes may switch
between both roles).

## Running Golem Network Renderer (GNR) in Ubuntu 15.04

### Installing Depedencies:

* Qt4 bingings for Python: `sudo apt-get install python-qt4`
* Twisted Qt4 integration: `sudo apt-get install python-qt4reactor`
* OpenEXR bindings for Python: download and unpack http://excamera.com/files/OpenEXR-1.2.0.tar.gz, then use `setup.py` inside
* ...
 
### Starting GNR

* Set environment variable `GOLEM` to `<path-to-golem-repo>/poc/golemPy` 
* Go to `$GOLEM/examples/gnr` and run `admMain.py`.

If the GUI does not look good at all and you see the following error in console:
```
QNativeImage: Unable to attach to shared memory segment. 

X Error: BadDrawable (invalid Pixmap or Window parameter) 9
  Major opcode: 62 (X_CopyArea)
  Resource id:  0x0
```
then set `QT_GRAPHICSSYSTEM=native` (see https://bbs.archlinux.org/viewtopic.php?id=200167).

