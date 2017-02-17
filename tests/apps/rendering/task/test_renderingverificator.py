from golem.testutils import TempDirFixture

from apps.rendering.task.verificator import RenderingVerificator
from apps.rendering.task.renderingtaskstate import AdvanceRenderingVerificationOptions


class TestRenderingVerificator(TempDirFixture):
    def test_box_start(self):
        rv = RenderingVerificator()

        rv.verification_options = AdvanceRenderingVerificationOptions()
        rv.verification_options.box_size = (5, 5)
        sizes = [(24, 12, 44, 20), (0, 0, 800, 600), (10, 150, 12, 152)]
        for size in sizes:
            for i in range(20):
                x, y = rv._get_box_start(*size)
                assert size[0] <= x <= size[2]
                assert size[1] <= y <= size[3]

    def test_get_part_size(self):
        rv = RenderingVerificator()
        rv.res_x = 800
        rv.res_y = 600
        assert rv._get_part_size("Subtask1", dict()) == (800, 600)

    def test_get_part_img_size(self):
        rv = RenderingVerificator()
        # rv._get_part_img_size("Subtask1", None, dict()) ==

