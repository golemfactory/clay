from customizer import Customizer


class RendererCustomizer(Customizer):
    def __init__(self, gui, logic, new_task_dialog):
        self.new_task_dialog = new_task_dialog
        self.renderer_options = new_task_dialog.renderer_options
        Customizer.__init__(self, gui, logic)
