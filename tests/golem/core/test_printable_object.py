
from unittest import TestCase

from golem.core.printable_object import PrintableObject


class PrintableObjectSpecimen(PrintableObject):
    def __init__(self, one, two):
        self.one = one
        self.two = two


class PrintableObjectTest(TestCase):
    def test_printable_object(self):
        po = PrintableObjectSpecimen('phobos', 'deimos')
        self.assertEqual(
            str(po), "PrintableObjectSpecimen <one: phobos, two: deimos>")
