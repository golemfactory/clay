import os
import abc
import logging
import math
import random
import OpenEXR, Imath
from PIL import Image

logger = logging.getLogger(__name__)

########################################################
class ImgRepr:
    @abc.abstractmethod
    def loadFromFile( self, file ):
        return

    @abc.abstractmethod
    def getPixel( self, (i, j) ):
        return

    @abc.abstractmethod
    def getSize( self ):
        return

########################################################
class PILImgRepr( ImgRepr ):
    def __init__( self ):
        self.img = None
        self.type = "PIL"

    def loadFromFile( self, file ):
        self.img = Image.open( file )
        self.img = self.img.convert('RGB')

    def getSize( self ):
        return self.img.size

    def getPixel( self, (i, j) ):
        return list( self.img.getpixel( (i, j) ) )

########################################################
class EXRImgRepr( ImgRepr ):
    def __init__( self ):
        self.img = None
        self.type = "EXR"
        self.dw = None
        self.pt = Imath.PixelType(Imath.PixelType.FLOAT)
        self.rgb = None

    def loadFromFile(self, file_ ):
        self.img = OpenEXR.InputFile( file_ )
        self.dw = self.img.header()['dataWindow']
        self.rgb = [Image.fromstring("F", self.getSize(), self.img.channel(c, self.pt) ) for c in "RGB"]

    def getSize( self ):
        return (self.dw.max.x - self.dw.min.x + 1, self.dw.max.y - self.dw.min.y + 1)

    def getPixel( self, (i, j)):
        return [ c.getpixel( (i, j) ) for c in self.rgb]


############################
def loadImg( file_ ):
    try:
        _, ext = os.path.splitext( file_ )
        if ext.upper() != ".EXR":
            img = PILImgRepr()
        else:
            img = EXRImgRepr()
        img.loadFromFile( file_ )
        return img
    except Exception, err:
        logger.warning( "Can't verify img file {}:{}".format( file_, str( err ) ) )
        return None

############################
def advanceVerifyImg( file_, resX, resY, startBox, boxSize, compareFile, cmpStartBox ):
    img = loadImg( file_ )
    cmpImg = loadImg( compareFile )
    if img is None or cmpImg is None:
        return False
    if img.getSize() != ( resX, resY ):
        return False
    if boxSize < 0 or boxSize > img.getSize():
        logger.error("Wrong box size for advance verification {}".format( boxSize ) )

    if isinstance( img, PILImgRepr ) and isinstance( cmpImg, PILImgRepr ):
        return __compareImgs( img, cmpImg, start1 = startBox, start2 = cmpStartBox, box = boxSize )
    else:
        return __compareImgs( img, cmpImg, maxCol = 1, start1 = startBox, start2 = cmpStartBox, box = boxSize)
    return True

############################
def verifyImg( file_, resX, resY ):
    img = loadImg( file_ )
    if img is None:
        return False
    return img.getSize() == ( resX, resY )

############################
def comparePILImgs( file1, file2 ):
    try:
        img1 = PILImgRepr()
        img1.loadFromFile( file1 )
        img2 = PILImgRepr()
        img2.loadFromFile( file2 )
        return __compareImgs( img1, img2 )
    except Exception, err:
        logger.info("Can't compare images {}, {}: {}".format( file1, file2, str( err ) ) )
        return False

############################
def compareEXRImgs( file1, file2 ):
    try:
        img1 = EXRImgRepr()
        img1.loadFromFile( file1 )
        img2 = EXRImgRepr()
        img2.loadFromFile( file2 )
        return __compareImgs( img1, img2, 1 )
    except Exception, err:
        logger.info("Can't compare images {}, {}: {}".format( file1, file2, str( err ) ) )
        return False

############################
def __compareImgs( img1, img2, maxCol = 255, start1 = (0, 0), start2 = (0, 0), box = None ):
    PSNR_ACCEPTABLE_MIN = 30
    mse = __countMSE( img1, img2, start1, start2, box )
    logger.debug( "MSE = {}".format( mse ) )
    if mse == 0:
        return True
    psnr = __countPSNR( mse, maxCol )
    logger.debug( "PSNR = {}".format( psnr ) )
    return psnr >= PSNR_ACCEPTABLE_MIN

############################
def __countPSNR( mse, max=255 ):
    return 20 * math.log10( max ) - 10 * math.log10( mse )

############################
def __countMSE( img1, img2, start1 = (0, 0), start2 = (0, 0), box = None):
    mse = 0
    if box is None:
        (resX, resY) = img1.getSize()
    else:
        (resX, resY) = box
    for i in range (0, resX ):
        for j in range( 0, resY ):
            [r1, g1, b1] = img1.getPixel( (start1[0] + i, start1[1] + j) )
            [r2, g2, b2] = img2.getPixel( (start2[0] + i, start2[1] + j) )
            mse += (r1 - r2)*(r1 - r2) + (g1 - g2)*(g1 - g2) + (b1 - b2)*(b1 - b2)

    mse /= resX * resY * 3
    return mse
