import logging

from PyQt4 import QtCore
from renderercustomizer import RendererCustomizer

logger = logging.getLogger(__name__)


class BlenderRenderDialogCustomizer(RendererCustomizer):

    def _setup_connections(self):
        self.gui.ui.buttonBox.rejected.connect(self.gui.window.close)
        self.gui.ui.buttonBox.accepted.connect(lambda: self.__change_renderer_options())

        QtCore.QObject.connect(self.gui.ui.framesCheckBox, QtCore.SIGNAL("stateChanged(int) "),
                                self.__frames_check_box_changed)

    def load_data(self):
        renderer = self.logic.get_renderer(u"Blender")

        self.gui.ui.framesCheckBox.setChecked(self.renderer_options.use_frames)
        self.gui.ui.framesLineEdit.setEnabled(self.renderer_options.use_frames)
        if self.renderer_options.use_frames:
            self.gui.ui.framesLineEdit.setText(self.frames_to_string(self.renderer_options.frames))
        else:
            self.gui.ui.framesLineEdit.setText("")

    def __frames_check_box_changed(self):
        self.gui.ui.framesLineEdit.setEnabled(self.gui.ui.framesCheckBox.isChecked())
        if self.gui.ui.framesCheckBox.isChecked():
            self.gui.ui.framesLineEdit.setText(self.frames_to_string(self.renderer_options.frames))

    def __change_renderer_options(self):
        self.renderer_options.use_frames = self.gui.ui.framesCheckBox.isChecked()
        if self.renderer_options.use_frames:
            frames = self.string_to_frames(self.gui.ui.framesLineEdit.text())
            if not frames:
                self.show_error_window("Wrong frame format. Frame list expected, e.g. 1;3;5-12.")
                return
            self.renderer_options.frames = frames
        self.new_task_dialog.set_renderer_options(self.renderer_options)
        self.gui.window.close()

    @staticmethod
    def frames_to_string(frames):
        s = ""
        last_frame = None
        interval = False
        try:
            for frame in sorted(frames):
                frame = int(frame)
                if frame < 0:
                    raise ValueError("Frame number must be greater or equal to 0")

                if last_frame is None:
                    s += str(frame)
                elif frame - last_frame == 1:
                    if not interval:
                        s += '-'
                        interval = True
                elif interval:
                    s += str(last_frame) + ";" + str(frame)
                    interval = False
                else:
                    s += ';' + str(frame)

                last_frame = frame

        except (ValueError, AttributeError, TypeError) as err:
            logger.error("Wrong frame format: {}".format(err))
            return ""

        if interval:
            s += str(last_frame)

        return s

    @staticmethod
    def string_to_frames(s):
        try:
            frames = []
            after_split = s.split(";")
            for i in after_split:
                inter = i.split("-")
                if len(inter) == 1:      # pojedyncza klatka (np. 5)
                    frames.append(int(inter[0]))
                elif len(inter) == 2:
                    inter2 = inter[1].split(",")
                    if len(inter2) == 1:      #przedzial klatek (np. 1-10)
                        start_frame = int(inter[0])
                        end_frame = int(inter[1]) + 1
                        frames += range(start_frame, end_frame)
                    elif len(inter2) == 2:    # co n-ta klata z przedzialu (np. 10-100,5)
                        start_frame = int(inter[0])
                        end_frame = int(inter2[0]) + 1
                        step = int(inter2[1])
                        frames += range(start_frame, end_frame, step)
                    else:
                        raise ValueError("Wrong frame step")
                else:
                    raise ValueError("Wrong frame range")
            return sorted(frames)
        except ValueError as err:
            logger.warning("Wrong frame format: {}".format(err))
            return []
        except (AttributeError, TypeError) as err:
            logger.error("Problem with change string to frame: {}".format(err))
            return []
