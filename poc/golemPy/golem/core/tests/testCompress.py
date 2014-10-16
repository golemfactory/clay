import unittest
import logging
import sys
import os

sys.path.append('./../../../')

from golem.core.Compress import compress, decompress, load, save


class TestCompress( unittest.TestCase ):
    def setUp( self ):
        logging.basicConfig(level=logging.DEBUG)

    def testCompress( self ):
        text = "12334231234434123452341234"
        c = compress( text )
        self.assertEqual( text, decompress( c ) )

    def testLoadSave( self ):
        text = "123afha  afhakjfh ajkajl 34 2 \n ajrfow 31\r \\ 23443a 4123452341234"
        c = compress( text )
        self.assertEqual( text, decompress( c ) )
        save( c, 'tezt.gz' )
        c2 = load( 'tezt.gz' )
        os.remove( 'tezt.gz' )
        self.assertEqual( text, decompress( c2 ) )

if __name__ == '__main__':
    unittest.main()