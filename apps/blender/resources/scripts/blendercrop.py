import bpy

for scene in bpy.data.scenes:

    scene.render.tile_x = 0
    scene.render.tile_y = 0
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    scene.render.border_max_x = 1.0
    scene.render.border_min_x = 0.0
    scene.render.border_min_y = 0.0
    scene.render.border_max_y = 1.0
    scene.render.use_compositing = False

#then render:
bpy.ops.render.render()

#and check if additional files aren't missing
bpy.ops.file.report_missing_files()