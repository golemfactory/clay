from pathlib import Path

from golem.core.common import get_golem_path
from golem.model import GenericKeyValue


class TermsOfUse:
    TERMS_ACCEPTED_KEY = 'terms_of_use_accepted'
    TERMS_VERSION = 1
    TERMS_PATH = Path('golem/TERMS.html')

    @classmethod
    def are_terms_accepted(cls):
        return GenericKeyValue.select()\
            .where(
                GenericKeyValue.key == cls.TERMS_ACCEPTED_KEY,
                GenericKeyValue.value == cls.TERMS_VERSION)\
            .count() > 0

    @classmethod
    def accept_terms(cls):
        entry, _ = GenericKeyValue.get_or_create(key=cls.TERMS_ACCEPTED_KEY)
        entry.value = cls.TERMS_VERSION
        entry.save()

    @classmethod
    def show_terms(cls):
        terms_path = Path(get_golem_path()) / cls.TERMS_PATH
        return terms_path.read_text()
