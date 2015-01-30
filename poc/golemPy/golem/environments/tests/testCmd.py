import unittest
import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.core.checkCmd import checkCmd

class TestCheckCmd( unittest.TestCase ):
    def testCheckCmd( self ):
        self.assertTrue( checkCmd( 'python' ) )
        self.assertFalse( checkCmd( 'afjaljl') )

if __name__ == '__main__':
    unittest.main()