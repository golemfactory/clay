import sys

class Environment:
    @classmethod
    def get_id(cls):
        return "DEFAULT"

    def __init__(self):
        self.software = []
        self.caps = []
        self.short_description = "Default environment for generic tasks without any additional requirements."
        self.long_description = ""
        self.accept_tasks = False

    def check_software(self):
        return True

    def check_caps(self):
        return True

    def supported(self):
        return True

    def is_accepted(self):
        return self.accept_tasks

    def description(self):
        desc = self.short_description + "\n"
        if self.caps or self.software:
            desc += "REQUIREMENTS\n\n"
            if self.caps:
                desc += "CAPS:\n"
                for c in self.caps:
                    desc += "\t* " + c + "\n"
                desc += "\n"
            if self.software:
                desc += "SOFTWARE:\n"
                for s in self.software:
                    desc += "\t * " + s + "\n"
                desc += "\n"
        if self.long_description:
            desc += "Additional informations:\n" + self.long_description
        return desc

    def is_windows(self):
        return sys.platform == 'win32'

    def isLinux(self):
        return sys.platform.startswith('linux')
