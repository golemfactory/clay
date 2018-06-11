# pylint: disable=import-error
import bpy

bpy.context.scene.cycles.device = 'GPU'

context = bpy.context
context.scene.cycles.device = 'GPU'
cycles_pref = bpy.context.user_preferences.addons['cycles'].preferences
device_types_by_preference = ['CUDA', 'NONE']
present_device_types = [dt[0] for dt in cycles_pref.get_device_types(context)]
for device_type in device_types_by_preference:
    if device_type in present_device_types:
        cycles_pref.compute_device_type = device_type
        break
for dev in cycles_pref.devices:
    dev.use = True
