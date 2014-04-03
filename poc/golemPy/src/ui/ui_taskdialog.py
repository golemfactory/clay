# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'taskdialog.ui'
#
# Created: Mon Mar 31 17:35:38 2014
#      by: PyQt4 UI code generator 4.10.3
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_TaskSpecDialog(object):
    def setupUi(self, TaskSpecDialog):
        TaskSpecDialog.setObjectName(_fromUtf8("TaskSpecDialog"))
        TaskSpecDialog.setWindowModality(QtCore.Qt.WindowModal)
        TaskSpecDialog.resize(301, 173)
        self.verticalLayout_2 = QtGui.QVBoxLayout(TaskSpecDialog)
        self.verticalLayout_2.setObjectName(_fromUtf8("verticalLayout_2"))
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setContentsMargins(-1, 0, -1, -1)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.label_3 = QtGui.QLabel(TaskSpecDialog)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 3, 0, 1, 1)
        self.label = QtGui.QLabel(TaskSpecDialog)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)
        self.label_2 = QtGui.QLabel(TaskSpecDialog)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)
        self.label_4 = QtGui.QLabel(TaskSpecDialog)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.gridLayout.addWidget(self.label_4, 0, 0, 1, 1)
        self.imgNameInput = QtGui.QLineEdit(TaskSpecDialog)
        self.imgNameInput.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.imgNameInput.setObjectName(_fromUtf8("imgNameInput"))
        self.gridLayout.addWidget(self.imgNameInput, 0, 1, 1, 1)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName(_fromUtf8("horizontalLayout"))
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.widthSpinBox = QtGui.QSpinBox(TaskSpecDialog)
        self.widthSpinBox.setMinimum(1)
        self.widthSpinBox.setMaximum(10000)
        self.widthSpinBox.setSingleStep(25)
        self.widthSpinBox.setProperty("value", 100)
        self.widthSpinBox.setObjectName(_fromUtf8("widthSpinBox"))
        self.horizontalLayout.addWidget(self.widthSpinBox)
        self.gridLayout.addLayout(self.horizontalLayout, 1, 1, 1, 1)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName(_fromUtf8("horizontalLayout_2"))
        spacerItem1 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.heightSpinBox = QtGui.QSpinBox(TaskSpecDialog)
        self.heightSpinBox.setMinimum(1)
        self.heightSpinBox.setMaximum(10000)
        self.heightSpinBox.setSingleStep(25)
        self.heightSpinBox.setProperty("value", 100)
        self.heightSpinBox.setObjectName(_fromUtf8("heightSpinBox"))
        self.horizontalLayout_2.addWidget(self.heightSpinBox)
        self.gridLayout.addLayout(self.horizontalLayout_2, 2, 1, 1, 1)
        self.horizontalLayout_3 = QtGui.QHBoxLayout()
        self.horizontalLayout_3.setObjectName(_fromUtf8("horizontalLayout_3"))
        spacerItem2 = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_3.addItem(spacerItem2)
        self.samplesPerPixelSpinBox = QtGui.QSpinBox(TaskSpecDialog)
        self.samplesPerPixelSpinBox.setMinimum(1)
        self.samplesPerPixelSpinBox.setMaximum(100000)
        self.samplesPerPixelSpinBox.setSingleStep(10)
        self.samplesPerPixelSpinBox.setProperty("value", 25)
        self.samplesPerPixelSpinBox.setObjectName(_fromUtf8("samplesPerPixelSpinBox"))
        self.horizontalLayout_3.addWidget(self.samplesPerPixelSpinBox)
        self.gridLayout.addLayout(self.horizontalLayout_3, 3, 1, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)
        spacerItem3 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem3)
        self.buttonBox = QtGui.QDialogButtonBox(TaskSpecDialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.verticalLayout.addWidget(self.buttonBox)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(TaskSpecDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), TaskSpecDialog.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), TaskSpecDialog.reject)
        QtCore.QMetaObject.connectSlotsByName(TaskSpecDialog)

    def retranslateUi(self, TaskSpecDialog):
        TaskSpecDialog.setWindowTitle(_translate("TaskSpecDialog", "Taks specification dialog", None))
        self.label_3.setText(_translate("TaskSpecDialog", "Samples per pixel", None))
        self.label.setText(_translate("TaskSpecDialog", "Image width", None))
        self.label_2.setText(_translate("TaskSpecDialog", "Image height", None))
        self.label_4.setText(_translate("TaskSpecDialog", "Image name", None))
        self.imgNameInput.setText(_translate("TaskSpecDialog", "default", None))

