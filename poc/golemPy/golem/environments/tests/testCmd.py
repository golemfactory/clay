import unittest
import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.environments.checkCmd import checkCmd

class TestCheckCmd( unittest.TestCase ):
    def testCheckCmd( self ):
        self.assertTrue( checkCmd( 'python' ) )
        self.assertTrue( checkCmd( 'python', noOutput=False ) )
        self.assertFalse( checkCmd( 'afjaljl') )
        self.assertFalse( checkCmd( 'wkeajkajf', noOutput=False ) )

if __name__ == '__main__':
    unittest.main()