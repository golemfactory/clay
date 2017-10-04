#  MiniLight Python : minimal global illumination renderer
#
#  Harrison Ainsworth / HXA7241 and Juraj Sukop : 2007-2008, 2013.
#  http://www.hxa.name/minilight


#from uuid import uuid4

SEED = 987654321
#SEED_MINS = [ 2, 8, 16, 128 ]

class Random(object):

    #def __init__(self):
    #    ul = uuid4().int
    #    ui = [ int((ul >> (i * 32)) & 0xFFFFFFFFL) for i in range(4) ]
    #    si = [ ui[i] if (ui[i] >= SEED_MINS[i]) else SEED for i in range(4) ]
    #    self.state0, self.state1, self.state2, self.state3 = si
    #    self.id = "%08X" % self.state3
    def __init__(self):
        self.state0 = self.state1 = self.state2 = self.state3 = SEED

    def int32u(self):
        self.state0 = (((self.state0 & 0xFFFFFFFE) << 18) & 0xFFFFFFFF) ^ \
                      ((((self.state0 <<  6) & 0xFFFFFFFF) ^ self.state0) >> 13)
        self.state1 = (((self.state1 & 0xFFFFFFF8) <<  2) & 0xFFFFFFFF) ^ \
                      ((((self.state1 <<  2) & 0xFFFFFFFF) ^ self.state1) >> 27)
        self.state2 = (((self.state2 & 0xFFFFFFF0) <<  7) & 0xFFFFFFFF) ^ \
                      ((((self.state2 << 13) & 0xFFFFFFFF) ^ self.state2) >> 21)
        self.state3 = (((self.state3 & 0xFFFFFF80) << 13) & 0xFFFFFFFF) ^ \
                      ((((self.state3 <<  3) & 0xFFFFFFFF) ^ self.state3) >> 12)
        return self.state0 ^ self.state1 ^ self.state2 ^ self.state3

    def real64(self):
        int0, int1 = self.int32u(), self.int32u()
        return (float((int0 < 2147483648) and int0 or (int0 - 4294967296)) *
            (1.0 / 4294967296.0)) + 0.5 + \
            (float(int1 & 0x001FFFFF) * (1.0 / 9007199254740992.0))
