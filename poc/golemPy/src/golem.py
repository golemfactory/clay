from message import *


if __name__ == "__main__":
    m1 = HelloMessage()
    sm1 = m1.serialize()
    m2 = PingMessage()
    sm2 = m2.serialize()
    m3 = PongMessage()
    sm3 = m3.serialize()

    print Message.deserialize(sm1)
    print Message.deserialize(sm2)
    print Message.deserialize(sm3)

