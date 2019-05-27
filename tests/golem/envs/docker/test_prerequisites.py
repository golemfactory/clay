from unittest import TestCase

from golem.envs.docker import DockerPrerequisites


class TestFromDict(TestCase):

    def test_missing_values(self):
        with self.assertRaises(TypeError):
            DockerPrerequisites.from_dict({})

    def test_extra_values(self):
        with self.assertRaises(TypeError):
            DockerPrerequisites.from_dict({
                'image': 'repo/img',
                'tag': '1.0',
                'extra': 'value'
            })

    def test_ok(self):
        prereqs = DockerPrerequisites.from_dict({
            'image': 'repo/img',
            'tag': '1.0'
        })
        self.assertEqual(prereqs, DockerPrerequisites(
            image='repo/img',
            tag='1.0'
        ))


class TestToDict(TestCase):

    def test_to_dict(self):
        prereqs_dict = DockerPrerequisites(
            image='repo/img',
            tag='1.0'
        ).to_dict()
        self.assertEqual(prereqs_dict, {
            'image': 'repo/img',
            'tag': '1.0'
        })
