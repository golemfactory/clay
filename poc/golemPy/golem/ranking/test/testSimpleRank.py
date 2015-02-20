import unittest
import sys
import os

sys.path.append( os.environ.get( 'GOLEM' ) )

from golem.ranking.simpleRank import SimpleRank

class TestSimpleRank( unittest.TestCase ):
    def testRank (self ):
        sr = SimpleRank()
        self.assertIsNone( sr.getNodeRank('abc') )
        sr.setNodeRank( 'abc', 1.0 )
        self.assertEquals( sr.getNodeRank('abc'), 1.0 )
        sr.setNodeRank( 'def', 0.3 )
        self.assertEquals( sr.getNodeRank('def'), 0.3 )
        sr.setNodeRank( 'ghi', -1.2 )
        self.assertEquals( sr.getNodeRank('ghi'), 0.0 )
        sr.setNodeRank( 'ghi', 3.0 )
        self.assertEquals( sr.getNodeRank('ghi'), 1.0 )

    def testNetworkRank( self ) :
        node1 = SimpleRank()
        node2 = SimpleRank()
        # 2 dolacza do sieci
        node2.setSeedRank( 'node1' )
        node1.setBasicNodeRank( 'node2' )
        print "Node1: {}".format( node1.ranking )
        print "Node2: {}".format( node2.ranking )
        # 3 dolacza do sieci z 1
        node3 = SimpleRank()
        node3.setSeedRank( 'node1' )
        node1.setBasicNodeRank( 'node3' )
        node2.changeNodeRank( 'node3', { 'node1': node1.getNodeRank('node3' ) } )
        node3.changeNodeRank( 'node2', { 'node2': node1.getNodeRank( 'node2' ) } )
        print "Node1: {}".format( node1.ranking )
        print "Node2: {}".format( node2.ranking )
        print "Node3: {}".format( node3.ranking )
        # 2 chce cos policzyc
        node1.changeNodeRank( 'node2', { 'node3': node1.getNodeRank('node2' ) } )
        node3.changeNodeRank( 'node2', { 'node1': node3.getNodeRank( 'node2' ) } )
        print "Node1: {}".format( node1.ranking )
        print "Node2: {}".format( node2.ranking )
        print "Node3: {}".format( node3.ranking )
        # 3 policzyla poprawnie
        node2.setNodeRank( 'node3', node2.getNodeRank( 'node3') + 0.1 )
        # 1 policzyla poprawnie
        node2.setNodeRank( 'node1', node2.getNodeRank( 'node1') + 0.1 )
        # 2 zaplacila
        node3.setNodeRank( 'node2', node3.getNodeRank( 'node2')  + 0.15 )
        node1.setNodeRank( 'node2', node1.getNodeRank( 'node2')  + 0.15 )
        print "Node1: {}".format( node1.ranking )
        print "Node2: {}".format( node2.ranking )
        print "Node3: {}".format( node3.ranking )
        # 4 dolacza do sieci
        node4 = SimpleRank()
        node4.setSeedRank( 'node2 ')
        node2.setBasicNodeRank( 'node4' )
        # 4 chce liczyc
        node1.changeNodeRank( 'node4', {'node2': node2.getNodeRank('node4'), 'node3': node3.getNodeRank('node4' ) } )
        node2.changeNodeRank( 'node4', {'node1': node1.getNodeRank('node4'), 'node3': node3.getNodeRank('node4' ) } )
        node3.changeNodeRank( 'node4', {'node2': node2.getNodeRank('node4'), 'node1': node1.getNodeRank('node4' ) } )
        node4.changeNodeRank( 'node1', {'node2': node2.getNodeRank('node1') } )
        node4.changeNodeRank( 'node2', {'node1': node1.getNodeRank('node2') } )
        node4.changeNodeRank( 'node3', {'node2': node2.getNodeRank('node3'), 'node1': node1.getNodeRank('node3' ) } )
        print "Node1: {}".format( node1.ranking )
        print "Node2: {}".format( node2.ranking )
        print "Node3: {}".format( node3.ranking )
        print "Node4: {}".format( node4.ranking )






