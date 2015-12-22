#############################################################################
##
## Copyright (c) 2014 Riverbank Computing Limited <info@riverbankcomputing.com>
## 
## This file is part of PyQt.
## 
## This file may be used under the terms of the GNU General Public
## License versions 2.0 or 3.0 as published by the Free Software
## Foundation and appearing in the files LICENSE.GPL2 and LICENSE.GPL3
## included in the packaging of this file.  Alternatively you may (at
## your option) use any later version of the GNU General Public
## License if such license has been publicly approved by Riverbank
## Computing Limited (or its successors, if any) and the KDE Free Qt
## Foundation. In addition, as a special exception, Riverbank gives you
## certain additional rights. These rights are described in the Riverbank
## GPL Exception version 1.1, which can be found in the file
## GPL_EXCEPTION.txt in this package.
## 
## If you are unsure which license is appropriate for your use, please
## contact the sales department at sales@riverbankcomputing.com.
## 
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
#############################################################################


import sys
import optparse

from PyQt4 import QtCore
from PyQt4.uic.driver import Driver


Version = "Python User Interface Compiler %s for Qt version %s" % (QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR)


if sys.hexversion >= 0x03000000:
    from PyQt4.uic.port_v3.invoke import invoke
else:
    from PyQt4.uic.port_v2.invoke import invoke


parser = optparse.OptionParser(usage="pyuic4 [options] <ui-file>",
        version=Version)
parser.add_option("-p", "--preview", dest="preview", action="store_true",
        default=False,
        help="show a preview of the UI instead of generating code")
parser.add_option("-o", "--output", dest="output", default="-", metavar="FILE",
        help="write generated code to FILE instead of stdout")
parser.add_option("-x", "--execute", dest="execute", action="store_true",
        default=False,
        help="generate extra code to test and display the class")
parser.add_option("-d", "--debug", dest="debug", action="store_true",
        default=False, help="show debug output")
parser.add_option("-i", "--indent", dest="indent", action="store", type="int",
        default=4, metavar="N",
        help="set indent width to N spaces, tab if N is 0 [default: 4]")
parser.add_option("-w", "--pyqt3-wrapper", dest="pyqt3_wrapper",
        action="store_true", default=False,
        help="generate a PyQt v3 style wrapper")

g = optparse.OptionGroup(parser, title="Code generation options")
g.add_option("--from-imports", dest="from_imports", action="store_true",
        default=False, help="generate imports relative to '.'")
g.add_option("--resource-suffix", dest="resource_suffix", action="store",
        type="string", default="_rc", metavar="SUFFIX",
        help="append SUFFIX to the basename of resource files [default: _rc]")
parser.add_option_group(g)

opts, args = parser.parse_args()

if len(args) != 1:
    sys.stderr.write("Error: one input ui-file must be specified\n")
    sys.exit(1)

sys.exit(invoke(Driver(opts, args[0])))
