class Environment:
    @classmethod
    def getId( cls ):
        return "DEFAULT"

    def __init__( self ):
        self.software = []
        self.caps = []
        self.shortDescription = "Default environment for generic tasks without any additional requirements."
        self.longDescription = ""

    def checkSoftware( self ):
        return True

    def checkCaps( self ):
        return True

    def supported( self ):
        return True

    def description( self ):
        desc = self.shortDescription + "\n"
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
        if self.longDescription:
            desc += "Additional informations:\n" + self.longDescription
        return desc