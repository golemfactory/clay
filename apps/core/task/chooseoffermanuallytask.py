from apps.core.task.coretask import CoreTask


class ChooseOfferManuallyTask(CoreTask):
    def is_offer_chosen_manually(self):
        return True
