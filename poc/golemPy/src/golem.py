from message import *
import uuid

if __name__ == "__main__":
    m1 = MessageHello(3030303, uuid.uuid1().get_hex())
    sm1 = m1.serialize()
    m2 = MessagePing()
    sm2 = m2.serialize()
    m3 = MessagePong()
    sm3 = m3.serialize()

    print Message.deserialize(sm1)
    print Message.deserialize(sm2)
    print Message.deserialize(sm3)
