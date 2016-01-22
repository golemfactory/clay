from gnr.customizers.customizer import Customizer
import logging

logger = logging.getLogger(__name__)


class AboutWindowCustomizer(Customizer):

    def _setup_connections(self):
        self.gui.ui.okButton.clicked.connect(self.gui.window.close)

    def load_data(self):
        name, version = self.logic.get_about_info()
        self.gui.ui.nameLabel.setText(name)
        self.gui.ui.versionLabel.setText(version)
