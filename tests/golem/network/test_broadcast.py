from freezegun import freeze_time
import peewee

from golem import model
from golem import testutils
from golem.network import broadcast


class SweepTestCase(testutils.DatabaseFixture):
    def setUp(self):
        super().setUp()
        self.privkey = b"/#\x99s\xff\x97Y\xf1\xa1\x03\xd4N4\x14F\x94\xbc\x87\xacr\\\x9f\xf6\x96'\xa5\x18\xeb\x19\xc04-"  # noqa pylint: disable=line-too-long

    @classmethod
    def test_basic(cls):
        broadcast.sweep()

    def test_single(self):
        model.Broadcast.create_and_sign(self.privkey, 1, b'1.3.3.7')
        broadcast.sweep()
        self.assertEqual(
            model.Broadcast.select(peewee.fn.Count()).scalar(),
            1,
        )

    def test_two(self):
        with freeze_time("2018-01-01 00:00:00") as frozen_time:
            # override a bug in freezegun that passes
            # frozen_time as first argument even to methods (before self)
            self.frozen_two(frozen_time)

    def frozen_two(self, frozen_time):
        model.Broadcast.create_and_sign(self.privkey, 1, b'1.3.3.7')
        # bug in freezegun puts frozen_time as first argument event in methods
        frozen_time.tick()  # pylint: disable=no-member
        model.Broadcast.create_and_sign(self.privkey, 1, b'3.1.3.3.7')
        broadcast.sweep()
        self.assertEqual(
            model.Broadcast.select(peewee.fn.Count()).scalar(),
            1,
        )
