from pathlib import Path

from golem.core.common import get_golem_path
from golem.model import GenericKeyValue


class TermsOfUseBase:
    ACCEPTED_KEY: str
    VERSION: int
    PATH: Path

    @classmethod
    def are_accepted(cls):
        return GenericKeyValue.select()\
            .where(
                GenericKeyValue.key == cls.ACCEPTED_KEY,
                GenericKeyValue.value == cls.VERSION)\
            .count() > 0

    @classmethod
    def accept(cls):
        entry, _ = GenericKeyValue.get_or_create(key=cls.ACCEPTED_KEY)
        entry.value = cls.VERSION
        entry.save()

    @classmethod
    def show(cls):
        terms_path = Path(get_golem_path()) / cls.PATH
        return terms_path.read_text()


class TermsOfUse(TermsOfUseBase):
    ACCEPTED_KEY = 'terms_of_use_accepted'
    VERSION = 4
    PATH = Path('golem/TERMS.html')


class ConcentTermsOfUse(TermsOfUseBase):
    ACCEPTED_KEY = 'concent_terms_of_use_accepted'
    VERSION = 1
    PATH = Path('golem/CONCENT_TERMS.html')
