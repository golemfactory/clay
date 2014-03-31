import sys
sys.path.append( '../')
sys.path.append( '../core')

from message import Message


if __name__ == "__main__":

    m = MessagePeerStatus( "test id", "some test data" )
    sm = m.serialize()
    print sm
    mm = Message.deserializeMessage( sm )
    print mm
