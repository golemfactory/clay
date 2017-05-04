import mock

from apps.blender.resources import scenefileeditor

from golem.testutils import TempDirFixture


class TestSceneFileEditor(TempDirFixture):
    def test_crop_file_generation_dummy(self):
        """Test blender script generation with simplistic template."""
        filepath = self.temp_file_name("tmpscene")
        with open(filepath, 'w') as f:
            f.write('''%(resolution_x)d
%(resolution_y)d
%(border_min_x).3f
%(border_max_x).3f
%(border_min_y).3f
%(border_max_y).3f
%(use_compositing)r''')
        # Unfortunatelly on windows you can't open tempfile second time
        # that's why we are leaving with statement and using delete=False.
        orig_path = scenefileeditor.BLENDER_CROP_TEMPLATE_PATH
        scenefileeditor.BLENDER_CROP_TEMPLATE_PATH = filepath
        try:
            result = scenefileeditor.generate_blender_crop_file(
                resolution=(1,2),
                borders_x=(3.01, 3.02),
                borders_y=(4.01, 4.02),
                use_compositing=True
            )
        finally:
            scenefileeditor.BLENDER_CROP_TEMPLATE_PATH = orig_path
        expected = '''1
2
3.010
3.020
4.010
4.020
True'''
        self.assertEqual(result, expected)

    def test_crop_file_generation_full(self):
        """Mocks blender by providing bpy and tests wether generated script acted as expected."""
        resolution = (1,2)
        borders_x = (3.01, 3.02)
        borders_y = (4.01, 4.02)
        use_compositing = True

        expected_attributes = {
            'resolution_x': resolution[0],
            'resolution_y': resolution[1],
            'border_min_x': borders_x[0],
            'border_max_x': borders_x[1],
            'border_min_y': borders_y[0],
            'border_max_y': borders_y[1],
            'use_compositing': use_compositing,

            'tile_x': 0,
            'tile_y': 0,
            'resolution_percentage': 100,
            'use_border': True,
            'use_crop_to_border': True,
        }
        result = scenefileeditor.generate_blender_crop_file(
                    resolution=resolution,
                    borders_x=borders_x,
                    borders_y=borders_y,
                    use_compositing=use_compositing
        )

        scene_m = mock.MagicMock()
        scene_m.render = mock.NonCallableMock()
        bpy_m = mock.MagicMock()
        bpy_m.data.scenes = [scene_m]
        bpy_m.ops.render.render.return_value = None
        bpy_m.ops.file.report_missing_files.return_value = None
        def hacked_import(*args, **kwargs):
            if args[0] == 'bpy':
                return bpy_m
            return __import__(*args, **kwargs)
        hacked_builtins = dict(__builtins__)
        hacked_builtins['__import__'] = hacked_import

        exec(result, {'__builtins__': hacked_builtins})

        # test scene attributes
        for name in expected_attributes:
            expected = expected_attributes[name]
            value = getattr(scene_m.render, name)
            self.assertEqual(value, expected, 'Value of scene.render.%s expected:%r got:%r' % (name, expected, value))

        # test calls
        bpy_m.ops.render.render.assert_called_once_with()
        bpy_m.ops.file.report_missing_files.assert_called_once_with()

    @mock.patch("golem.resource.dirmanager")
    def test_crop_template_path_error(self, mock_manager):
        mock_manager.find_task_script.return_value = None
        with self.assertRaises(IOError):
            reload(scenefileeditor)

    def tearDown(self):
        super(TestSceneFileEditor, self).tearDown()
        reload(scenefileeditor)
