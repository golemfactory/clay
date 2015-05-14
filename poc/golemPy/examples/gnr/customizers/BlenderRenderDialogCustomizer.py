import logging

from PyQt4 import QtCore
from PyQt4.QtGui import QMessageBox
from examples.gnr.ui.BlenderRenderDialog import BlenderRenderDialog

logger = logging.getLogger(__name__)

class BlenderRenderDialogCustomizer:
    #############################
    def __init__( self, gui, logic, newTaskDialog ):
        assert isinstance( gui, BlenderRenderDialog )

        self.gui = gui
        self.logic = logic
        self.newTaskDialog = newTaskDialog

        self.rendererOptions = newTaskDialog.rendererOptions

        self.__init()
        self.__setupConnections()

    #############################
    def __init( self ):
        renderer = self.logic.getRenderer( u"Blender" )

        self.gui.ui.engineComboBox.addItems( self.rendererOptions.engineValues )
        engineItem = self.gui.ui.engineComboBox.findText( self.rendererOptions.engine )
        if engineItem != -1:
            self.gui.ui.engineComboBox.setCurrentIndex( engineItem )
        else:
            logger.error( "Wrong engine type " )

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
        index = self.gui.ui.engineComboBox.currentIndex()
        self.rendererOptions.engine = u"{}".format( self.gui.ui.engineComboBox.itemText( index ) )
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
                if len( inter ) == 1:      # pojedyncza klatka (np. 5)
                    frames.append( int ( inter[0] ) )
                elif len( inter ) == 2:
                    inter2 = inter[1].split(",")
                    if len( inter2 ) == 1:      #przedzial klatek (np. 1-10)
                        startFrame = int( inter[0] )
                        endFrame = int( inter[1] ) + 1
                        frames += range( startFrame, endFrame )
                    elif len ( inter2 )== 2:    # co n-ta klata z przedzialu (np. 10-100,5)
                        startFrame = int( inter[0] )
                        endFrame = int( inter2[0] ) + 1
                        step = int( inter2[1] )
                        frames += range( startFrame, endFrame, step )
                    else:
                        raise
                else:
                    raise
            return frames
        except:
            return []
