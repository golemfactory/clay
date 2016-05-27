import unittest

from gnr.customizers.blenderrenderdialogcustomizer import BlenderRenderDialogCustomizer


class TestFramesConversion(unittest.TestCase):
    def test_frames_to_string(self):
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1, 4, 3, 2]), "1-4")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1]), "1")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(range(10)), "0-9")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(range(13, 16) + range(10)), "0-9;13-15")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([1, 3, 4, 5, 10, 11]), '1;3-5;10-11')
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([0, 5, 10, 15]), '0;5;10;15')
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["abc", "5"]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["1", "5"]), "1;5")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string(["5", "2", "1", "3"]), "1-3;5")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([-1]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string([2, 3, -1]), "")
        self.assertEqual(BlenderRenderDialogCustomizer.frames_to_string("ABC"), "")

    def test_string_to_frames(self):
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1-4'), range(1, 5))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('5-8;1-3'), [1, 2, 3, 5, 6, 7, 8])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1 - 4'), range(1, 5))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-9; 13-15'), range(10) + range(13, 16))
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;23'), [0, 5, 10, 15, 23])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;23-25;26'),
                         [0, 5, 10, 15, 23, 24, 25, 26])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('abc'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('0-15,5;abc'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames(0), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('5-8;1-2-3'), [])
        self.assertEqual(BlenderRenderDialogCustomizer.string_to_frames('1-100,2,3'), [])




