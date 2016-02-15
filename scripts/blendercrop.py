import bpy

for scene in bpy.data.scenes:

    scene.render.tile_x = 16
    scene.render.tile_y = 16
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.use_border = True
    scene.render.use_crop_to_border = True

    n = 3
    m = 2

    if (n * m) == 0:
        scene.render.border_max_x = 1.0
        scene.render.border_min_x = 0.0
        scene.render.border_min_y = 0.0
        scene.render.border_max_y = 1.0
        bpy.ops.render.render()
    else:
        cnt = 0
        for i in [x * 1.0/n for x in range(n)]:
            for j in [x * 1.0/m for x in range(m)]:
                scene.render.border_max_x = i + 1.0/n
                scene.render.border_min_x = i
                scene.render.border_min_y = j
                scene.render.border_max_y = j + 1.0/m
                cnt += 1
                scene.render.filepath = "res_{}.png".format(cnt)
                bpy.ops.render.render(write_still=True)
