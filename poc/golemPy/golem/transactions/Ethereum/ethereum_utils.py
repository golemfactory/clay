# The MIT License (MIT)
#
# Copyright (c) 2013 Geff Obscura
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from rlp.sedes import big_endian_int
from rlp.utils import str_to_bytes


def to_string(value):
    return str(value)

is_numeric = lambda x: isinstance(x, (int, long))
is_string = lambda x: isinstance(x, (str, unicode))

big_endian_to_int = lambda x: big_endian_int.deserialize(str_to_bytes(x).lstrip(b'\x00'))
int_to_big_endian = lambda x: big_endian_int.serialize(x)

TT256 = 2 ** 256


def zpad(x, l):
    return b'\x00' * max(0, l - len(x)) + x


def encode_int(v):
    """encodes an integer into serialization"""
    if not is_numeric(v) or v < 0 or v >= TT256:
        raise Exception("Integer invalid or out of range: %r" % v)
    return int_to_big_endian(v)


def ceil32(x):
    return x if x % 32 == 0 else x + 32 - (x % 32)


def to_string_for_regexp(value):
    return str(value)
