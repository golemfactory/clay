import logging

from PyQt4 import QtCore
from PyQt4.QtGui import QFileDialog, QMessageBox
from examples.gnr.ui.VRayDialog import VRayDialog

logger = logging.getLogger(__name__)

class VRayDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, VRayDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"VRay" )
        self.gui.ui.rtComboBox.addItems( self.rendererOptions.rtEngineValues.values() )
        rtEngineItem = self.gui.ui.rtComboBox.findText( self.rendererOptions.rtEngineValues[ self.rendererOptions.rtEngine ] )
        if rtEngineItem != -1:
            self.gui.ui.rtComboBox.setCurrentIndex( rtEngineItem )
        else:
            logger.error("Wrong renderer type ")

        self.gui.ui.framesCheckBox.setChecked( self.rendererOptions.useFrames )
        self.gui.ui.framesLineEdit.setEnabled( self.rendererOptions.useFrames )
        if self.rendererOptions.useFrames:
            self.gui.ui.framesLineEdit.setText( self.__framesToString( self.rendererOptions.frames ) )
        else:
            self.gui.ui.framesLineEdit.setText("")

    #############################
    def __setupConnections( self ):
        self.gui.ui.buttonBox.rejected.connect( self.gui.window.close )
        self.gui.ui.buttonBox.accepted.connect( lambda: self.__changeRendererOptions() )

        QtCore.QObject.connect( self.gui.ui.framesCheckBox, QtCore.SIGNAL( "stateChanged( int ) " ),
                                self.__framesCheckBoxChanged )

    #############################
    def __framesCheckBoxChanged( self ):
        self.gui.ui.framesLineEdit.setEnabled( self.gui.ui.framesCheckBox.isChecked() )
        if self.gui.ui.framesCheckBox.isChecked():
            self.gui.ui.framesLineEdit.setText( self.__framesToString( self.rendererOptions.frames ) )

    #############################
    def __changeRendererOptions( self ):
        index = self.gui.ui.rtComboBox.currentIndex()
        rtEngine = u"{}".format( self.gui.ui.rtComboBox.itemText( index ) )
        changed = False
        for key, value in self.rendererOptions.rtEngineValues.iteritems():
            if rtEngine == value:
                self.rendererOptions.rtEngine = key
                changed = True
        if not changed:
            logger.error( "Wrong rtEngine value: {}".format( rtEngine ) )
        self.rendererOptions.useFrames = self.gui.ui.framesCheckBox.isChecked()
        if self.rendererOptions.useFrames:
            frames = self.__stringToFrames( self.gui.ui.framesLineEdit.text() )
            if not frames:
                QMessageBox().critical(None, "Error", "Wrong frame format. Frame list expected, e.g. 1;3;5-12. ")
                return
            self.rendererOptions.frames = frames
        self.newTaskDialog.setRendererOptions( self.rendererOptions )
        self.gui.window.close()

   #############################
    def __framesToString( self, frames ):
        s = ""
        lastFrame = None
        interval = False
        for frame in sorted( frames ):
            try:
                frame = int ( frame )
                if frame < 0:
                    raise

                if lastFrame == None:
                    s += str( frame )
                elif frame - lastFrame == 1:
                    if not interval:
                        s += '-'
                        interval = True
                elif interval:
                    s += str( lastFrame ) + ";" + str( frame )
                    interval = False
                else:
                    s += ';' + str( frame )

                lastFrame = frame

            except:
                logger.error("Wrong frame format")
                return ""

        if interval:
            s += str( lastFrame )

        return s

    #############################
    def __stringToFrames( self, s ):
        try:
            frames = []
            splitted = s.split(";")
            for i in splitted:
                inter = i.split("-")
                if len ( inter ) == 1:
                    frames.append( int ( inter[0] ) )
                elif len( inter ) == 2:
                    frames += range( int( inter[0] ), int( inter[1] ) + 1 )
                else:
                    raise
            return frames
        except:
            return []
