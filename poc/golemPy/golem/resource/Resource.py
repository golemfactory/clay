
import logging

from golem.core.simplehash import SimpleHash
from golem.resource.DirManager import splitPath

import os
import zipfile

logger = logging.getLogger(__name__)

class TaskResourceHeader:

    def __eq__(self, other):
        if self.dirName != other.dirName:
            return False
        if self.filesData != other.filesData:
            return False
        if len(self.subDirHeaders) != len(other.subDirHeaders):
            return False
        sub1 = sorted(self.subDirHeaders, lambda x: x.dirName)
        sub2 = sorted(other.subDirHeaders, lambda x: x.dirName)
        for i in range(len(self.subDirHeaders)):
            if not (sub1[i] == sub2[i]):
                return False
        return True


    ####################
    @classmethod
    def build(cls, relativeRoot, absoluteRoot):
        return cls.__build(relativeRoot, absoluteRoot)

    ####################
    @classmethod
    def buildFromChosen(cls, dirName, absoluteRoot, choosenFiles = None):
        curTh = TaskResourceHeader(dirName)

        absDirs = splitPath(absoluteRoot)

        for f in choosenFiles:

            dir, fileName = os.path.split(f)
            dirs = splitPath(dir)[len(absDirs):]

            lastHeader = curTh

            for d in dirs:

                childSubDirHeader = TaskResourceHeader(d)
                if lastHeader.__hasSubHeader(d):
                    lastHeader = lastHeader.__getSubHeader(d)
                else:
                    lastHeader.subDirHeaders.append(childSubDirHeader)
                    lastHeader = childSubDirHeader

            hsh = SimpleHash.hash_file_base64(f)
            lastHeader.filesData.append((fileName, hsh))

        return curTh

    ####################
    @classmethod
    def __build(cls, dirName, absoluteRoot, choosenFiles = None):
        curTh = TaskResourceHeader(dirName)

        dirs  = [ name for name in os.listdir(absoluteRoot) if os.path.isdir(os.path.join(absoluteRoot, name)) ]
        files = [ name for name in os.listdir(absoluteRoot) if os.path.isfile(os.path.join(absoluteRoot, name)) ]

        filesData = []
        for f in files:
            if choosenFiles and os.path.join(absoluteRoot, f) not in  choosenFiles:
                continue
            hsh = SimpleHash.hash_file_base64(os.path.join(absoluteRoot, f))

            filesData.append((f, hsh))

        #print "{}, {}, {}".format(relativeRoot, absoluteRoot, filesData)

        curTh.filesData = filesData

        subDirHeaders = []
        for d in dirs:
            childSubDirHeader = cls.__build(d, os.path.join(absoluteRoot, d), choosenFiles)
            subDirHeaders.append(childSubDirHeader)

        curTh.subDirHeaders = subDirHeaders
        #print "{} {} {}\n".format(absoluteRoot, len(subDirHeaders), len(filesData))

        return curTh

    ####################
    @classmethod
    def buildHeaderDeltaFromChosen(cls, header, absoluteRoot, chosenFiles = None):
        assert isinstance(header, TaskResourceHeader)
        curTh = TaskResourceHeader(header.dirName)

        absDirs = splitPath(absoluteRoot)

        for file in chosenFiles:

            dir, fileName = os.path.split(file)
            dirs = splitPath(dir)[len(absDirs):]

            lastHeader = curTh
            lastRefHeader = header

            lastHeader, lastRefHeader, refHeaderFound = cls.__resolveDirs(dirs, lastHeader, lastRefHeader)

            hsh = SimpleHash.hash_file_base64(file)
            if refHeaderFound:
                if lastRefHeader.__hasFile(fileName):
                    if hsh == lastRefHeader.__getFileHash(fileName):
                        continue
            lastHeader.filesData.append((fileName, hsh))

        return curTh

    ####################
    @classmethod
    def buildPartsHeaderDeltaFromChosen(cls, header, absoluteRoot, resParts):
        assert isinstance(header, TaskResourceHeader)
        curTh = TaskResourceHeader(header.dirName)
        absDirs = splitPath (absoluteRoot)
        deltaParts = []

        for file_, parts in resParts.iteritems():
            dir, fileName = os.path.split(file_)
            dirs = splitPath(dir) [ len(absDirs): ]

            lastHeader = curTh
            lastRefHeader = header

            lastHeader, lastRefHeader, refHeaderFound = cls.__resolveDirs(dirs, lastHeader, lastRefHeader)

            hsh = SimpleHash.hash_file_base64(file_)
            if refHeaderFound:
                if lastRefHeader.__hasFile(fileName):
                    if hsh == lastRefHeader.__getFileHash(fileName):
                        continue
            lastHeader.filesData.append((fileName, hsh, parts))
            deltaParts += parts

        return curTh, deltaParts

    ####################
    # Dodaje tylko te pola, ktorych nie ma w headerze (i/lub nie zgadzaj? si? hasze)
    @classmethod
    def buildHeaderDeltaFromHeader(cls, header, absoluteRoot, choosenFiles):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResourceHeader(header.dirName)

        dirs  = [ name for name in os.listdir(absoluteRoot) if os.path.isdir(os.path.join(absoluteRoot, name)) ]
        files = [ name for name in os.listdir(absoluteRoot) if os.path.isfile(os.path.join(absoluteRoot, name)) ]

        for d in dirs:
            if header.__hasSubHeader(d):
                curTr.subDirHeaders.append(
                    cls.buildHeaderDeltaFromHeader(header.__getSubHeader(d), os.path.join(absoluteRoot, d), choosenFiles))
            else:
                curTr.subDirHeaders.append(cls.__build(d, os.path.join(absoluteRoot, d), choosenFiles))

        for f in files:
            if choosenFiles and os.path.join(absoluteRoot, f) not in choosenFiles:
                continue

            fileHash = 0
            if header.__hasFile(f):
                fileHash = SimpleHash.hash_file_base64(os.path.join(absoluteRoot, f))

                if fileHash == header.__getFileHash(f):
                    continue

            if not fileHash:
                fileHash = SimpleHash.hash_file_base64(os.path.join(absoluteRoot, f))

            curTr.filesData.append((f, fileHash))

        return curTr

    @classmethod
    def __resolveDirs(self, dirs, lastHeader, lastRefHeader):
        refHeaderFound = True
        for d in dirs:

            childSubDirHeader = TaskResourceHeader(d)

            if lastHeader.__hasSubHeader(d):
                lastHeader = lastHeader.__getSubHeader(d)
            else:
                lastHeader.subDirHeaders.append(childSubDirHeader)
                lastHeader = childSubDirHeader

            if refHeaderFound:
                if lastRefHeader.__hasSubHeader(d):
                    lastRefHeader = lastRefHeader.__getSubHeader(d)
                else:
                    refHeaderFound = False
        return lastHeader, lastRefHeader, refHeaderFound


    ####################
    def __init__(self, dirName):
        self.subDirHeaders  = []
        self.filesData      = []
        self.dirName        = dirName

    ####################
    def toString(self):
        out = u"\nROOT '{}' \n".format(self.dirName)

        if len(self.subDirHeaders) > 0:
            out += u"DIRS \n"
            for d in self.subDirHeaders:
                out += u"    {}\n".format(d.dirName)

        if len(self.filesData) > 0:
            out += u"FILES \n"
            for f in self.filesData:
                if len(f) > 2:
                    out += u"    {} {} {}".format(f[ 0 ], f[ 1 ], f[2])
                else:
                    out += u"    {} {}".format(f[ 0 ], f[ 1 ])

        for d in self.subDirHeaders:
            out += d.toString()

        return out


    ####################
    def __str__(self):
        return self.toString()

    ####################
    def hash(self):
        return SimpleHash.hash_base64(self.toString().encode('utf-8'))

    def __hasSubHeader(self, dirName):
        return dirName in [ sh.dirName for sh in self.subDirHeaders ]

    def __hasFile(self, file):
        return file in [ f[0] for f in self.filesData ]

    def __getSubHeader(self, dirName):
        idx = [ sh.dirName for sh in self.subDirHeaders ].index(dirName)
        return self.subDirHeaders[ idx ]

    def __getFileHash(self, file):
        idx = [ f[0] for f in self.filesData ].index(file)
        return self.filesData[ idx ][1]

class TaskResource:

    ####################
    @classmethod
    def __build(cls, dirName, absoluteRoot):
        curTh = TaskResource(dirName)

        dirs  = [ name for name in os.listdir(absoluteRoot) if os.path.isdir(os.path.join(absoluteRoot, name)) ]
        files = [ name for name in os.listdir(absoluteRoot) if os.path.isfile(os.path.join(absoluteRoot, name)) ]

        filesData = []
        for f in files:
            fileData = cls.readFile(os.path.join(absoluteRoot, f))
            hsh = SimpleHash.hash_base64(fileData)
            filesData.append((f, hsh, fileData))

        #print "{}, {}, {}".format(relativeRoot, absoluteRoot, filesData)

        curTh.filesData = filesData

        subDirResources = []
        for d in dirs:
            childSubDirHeader = cls.__build(d, os.path.join(absoluteRoot, d))
            subDirResources.append(childSubDirHeader)

        curTh.subDirResources = subDirResources
        #print "{} {} {}\n".format(absoluteRoot, len(subDirHeaders), len(filesData))

        return curTh

    ####################
    @classmethod
    def readFile(cls, fileName):
        try:
            f = open(fileName, "rb")
            data = f.read()
        except Exception as ex:
            logger.error(str(ex))
            return None

        return data

    ####################
    @classmethod
    def writeFile(cls, fileName, data):
        try:
            f = open(fileName, "wb")
            f.write(data)
        except Exception as ex:
            logger.error(str(ex))

    ####################
    @classmethod
    def validateHeader(cls, header, absoluteRoot):
        assert isinstance(header, TaskResourceHeader)

        for f in header.filesData:
            fname = os.path.join(absoluteRoot, f[ 0 ])

            if not os.path.exists(fname):
                return False, "File {} does not exist".format(fname)

            if not os.path.isfile(fname):
                return False, "Entry {} is not a file".format(fname)

        for dh in header.subDirHeaders:
            validated, msg = cls.validateHeader(dh, os.path.join(absoluteRoot, dh.dirName))

            if not validated:
                return validated, msg

        return True, None

    ####################
    @classmethod
    def buildFromHeader(cls, header, absoluteRoot):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResource(header.dirName)

        filesData = []
        for f in header.filesData:
            fname = os.path.join(absoluteRoot, f[ 0 ])
            fdata = cls.readFile(fname)
            
            if fdata is None:
                return None

            filesData.append((f[ 0 ], f[ 1 ], fdata))

        curTr.filesData = filesData

        subDirResources = []
        for sdh in header.subDirHeaders:
            subDirRes = cls.buildFromHeader(sdh, os.path.join(absoluteRoot, sdh.dirName))

            if subDirRes is None:
                return None
            
            subDirResources.append(subDirRes)

        curTr.subDirResources = subDirResources

        return curTr         ####################
    # Dodaje tylko te pola, ktorych nie ma w headerze (i/lub nie zgadzaj? si? hasze)
    @classmethod
    def buildDeltaFromHeader(cls, header, absoluteRoot):
        assert isinstance(header, TaskResourceHeader)

        curTr = TaskResource(header.dirName)

        dirs  = [ name for name in os.listdir(absoluteRoot) if os.path.isdir(os.path.join(absoluteRoot, name)) ]
        files = [ name for name in os.listdir(absoluteRoot) if os.path.isfile(os.path.join(absoluteRoot, name)) ]

        for d in dirs:
            if d in [ sdh.dirName for sdh in header.subDirHeaders ]:
                idx = [ sdh.dirName for sdh in header.subDirHeaders ].index(d)
                curTr.subDirResources.append(cls.buildDeltaFromHeader(header.subDirHeaders[ idx ], os.path.join(absoluteRoot, d)))
            else:
                curTr.subDirResources.append(cls.__build(d, os.path.join(absoluteRoot, d)))

        for f in files:
            if f in [ file[ 0 ] for file in header.filesData ]:
                idx = [ file[ 0 ] for file in header.filesData ].index(f)
                if SimpleHash.hash_file_base64(os.path.join(absoluteRoot, f)) == header.filesData[ idx ][ 1 ]:
                    continue

            fdata = cls.readFile(os.path.join(absoluteRoot, f))
            
            if fdata is None:
                return None

            curTr.filesData.append((f, SimpleHash.hash_base64(fdata), fdata))

        return curTr

    ####################
    def extract(self, toPath):
        for dir in self.subDirResources:
            if not os.path.exists(os.path.join(toPath, dir.dirName)):
                os.makedirs(os.path.join(toPath, dir.dirName))

            dir.extract(os.path.join(toPath, dir.dirName))

        for f in self.filesData:
            if not os.path.exists(os.path.join(toPath, f[ 0 ])) or SimpleHash.hash_file_base64(os.path.join(toPath, f[ 0 ])) != f[ 1 ]:
                self.writeFile(os.path.join(toPath, f[ 0 ]), f[ 2 ])

    ####################
    def __init__(self, dirName):
        self.filesData          = []
        self.subDirResources    = []
        self.dirName            = dirName

    ####################
    def toString(self):
        out = "\nROOT '{}' \n".format(self.dirName)

        if len(self.subDirResources) > 0:
            out += "DIRS \n"
            for d in self.subDirResources:
                out += "    {}\n".format(d.dirName)

        if len(self.filesData) > 0:
            out += "FILES \n"
            for f in self.filesData:
                out += "    {:10} {} {}".format(len(f[ 2 ]), f[ 0 ], f[ 1 ])

        for d in self.subDirResources:
            out += d.toString()

        return out

    ####################
    def __str__(self):
        return self.toString()

import unicodedata
import string

validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)

def removeDisallowedFilenameChars(filename):
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleanedFilename if c in validFilenameChars)

####################
def compressDir(root_path, header, outputDir):

    outputFile = removeDisallowedFilenameChars(header.hash().strip().decode('unicode-escape') + ".zip")

    outputFile = os.path.join(outputDir, outputFile)

    zipf = zipfile.ZipFile(outputFile, 'w', compression = zipfile.ZIP_DEFLATED, allowZip64 = True)

    currWorkingDir = os.getcwd()
    os.chdir(root_path)
    logger.debug("Working directory {}".format(os.getcwd()))

    try:
        compressDirImpl("", header, zipf)

        zipf.close()
    finally:
        os.chdir(currWorkingDir)
        logger.debug("Return to prev working directory {}".format(os.getcwd()))

    return outputFile

####################
def decompressDir(root_path, zipFile):

    zipf = zipfile.ZipFile(zipFile, 'r', allowZip64 = True)

    zipf.extractall(root_path)

####################
def compressDirImpl(root_path, header, zipf):

    for sdh in header.subDirHeaders:
        compressDirImpl(os.path.join(root_path, sdh.dirName), sdh, zipf)
        
    for fdata in header.filesData:
        zipf.write(os.path.join(root_path, fdata[ 0 ]))

####################
def prepareDeltaZip(rootDir, header, outputDir, choosenFiles = None):
    #deltaHeader = TaskResourceHeader.buildHeaderDeltaFromHeader(header, rootDir, choosenFiles)
    deltaHeader = TaskResourceHeader.buildHeaderDeltaFromChosen(header, rootDir, choosenFiles)
    return compressDir(rootDir, deltaHeader, outputDir)


# if __name__ == "__main__":
#
#     def walk_test(root):
#         for root, dirs, files in os.walk(root, topdown=True):
#             for name in dirs:
#                 #print("D", os.path.join(root, name))
#                 print("D", root, name)
#             #for name in files:
#             #    print("F", os.path.join(root, name))
#
#     def printAndPause(i):
#         import msvcrt as m
#         def wait():
#             m.getch()
#
#         print "{}".format(i)
#         wait()
#
#     def main():
#         t = TaskResourceHeader("test", "resource_test_dir\\test")
#         print t
#         t = 0
#
#     import glob
#     files = glob.glob(os.path.join("input_64", "*.exr"))
#
#     print files
#     from golem.databuffer import DataBuffer
#
#     db = DataBuffer()
#     import gc
#     while True:
#         for f in files:
#             if True:
#                 import cPickle
#                 import Compress
#                 from golem.Message import MessageTaskComputed, Message
#                 fh = open(f, 'rb')
#                 printAndPause(0)
#                 fileData = Compress.compress(fh.read())
#                 printAndPause(1)
#                 #fileData = fh.read()
#                 #data = cPickle.dumps((f, fileData))
#                 data = fileData
#                 printAndPause(2)
#                 m = MessageTaskComputed("", {}, data)
#                 printAndPause(3)
#                 serializedMess = m.serialize_with_header()
#                 printAndPause(4)
#                 db.append_string(serializedMess)
#                 printAndPause(5)
#                 desMess = Message.deserialize(db)
#                 printAndPause(6)
#                 data = desMess[0].result
#                 printAndPause(7)
#                 #(name, data) = cPickle.loads(desMess[0].result)
#                 d = Compress.decompress(data)
#                 printAndPause(8)
#                 out = open("resdupa", 'wb')
#                 printAndPause(9)
#                 out.write(d)
#                 printAndPause(10)
#                 out.close()
#                 printAndPause(11)
#
#             gc.collect()
#             printAndPause(12)
#
#         #tr = pickle.loads(trp)
#         #fh = open(os.path.join(tmpDir, tr[ 0 ]), "wb")
#         #fh.write(decompress(tr[ 1 ]))
#         #fh.close()
#
#     #th = TaskResourceHeader.build("test", "resource_test_dir\\test_empty")
#
#     #prepareDeltaZip("resource_test_dir\\test", th, "resource_test_dir.zip")
#
#     #print th
#
#     #print "Entering task testing zone"
#     #v, m = TaskResource.validateHeader(th, "resource_test_dir\\test" )
#
#     #if not v:
#     #    print m
#     #else:
#     #    tr = TaskResource.buildFromHeader(th, "resource_test_dir\\test")
#     #    print tr
#
#     #    trd = TaskResource.buildDeltaFromHeader(th, "resource_test_dir\\test")
#
#     #    trd.extract("out")
#
#     #    save(trd, "trd.zip")
#
#     #    loadedTrd = load("trd.zip")
#     #    print trd
#
#     #    loadedTrd.extract("out")
#
#
#
#     #walk_test(".")
#     #main()
