from typing import List

import golem.model


def _repository_from_image_name(image_name: str) -> str:
    return image_name.rsplit('/', maxsplit=1)[0]


class Whitelist:

    @staticmethod
    def get_all() -> List[str]:
        return [
            whitelisted.repository for whitelisted in
            golem.model.DockerWhitelist.select().execute()
        ]

    @classmethod
    def add(cls, image_name: str) -> bool:
        """
        Returns False if the entry was already on the whitelist.
        """
        repository = _repository_from_image_name(image_name)
        if cls.is_whitelisted(repository):
            return False
        golem.model.DockerWhitelist.create(repository=repository)
        return True

    @classmethod
    def remove(cls, image_name: str) -> bool:
        """
        Return False is the entry was not present on the whitelist.
        """
        repository = _repository_from_image_name(image_name)
        if not cls.is_whitelisted(repository):
            return False
        golem.model.DockerWhitelist.delete().where(
            golem.model.DockerWhitelist.repository == repository,
        ).execute()
        return True

    @staticmethod
    def is_whitelisted(image_name: str) -> bool:
        repository = _repository_from_image_name(image_name)
        query = \
            golem.model.DockerWhitelist.select().where(
                golem.model.DockerWhitelist.repository == repository,
            )
        return query.exists()
