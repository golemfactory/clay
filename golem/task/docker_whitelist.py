import golem.model


class DockerWhitelist:
    @classmethod
    def add(cls, repository: str) -> bool:
        """
        Returns False if the entry was already on the whitelist.
        """
        if cls.is_whitelisted(repository):
            return False
        golem.model.DockerWhitelist.create(repository=repository)
        return True

    @classmethod
    def remove(cls, repository: str) -> bool:
        """
        Return False is the entry was not present on the whitelist.
        """
        if not cls.is_whitelisted(repository):
            return False
        golem.model.DockerWhitelist.delete().where(
            golem.model.DockerWhitelist.repository == repository,
        ).execute()
        return True

    @staticmethod
    def is_whitelisted(repository: str) -> bool:
        query = \
            golem.model.DockerWhitelist.select().where(
                golem.model.DockerWhitelist.repository == repository,
            )
        return query.exists()
