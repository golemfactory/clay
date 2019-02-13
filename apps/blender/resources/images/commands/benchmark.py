import time

from pathlib import Path

from scripts import blender_render


def benchmark(
        work_dir: Path,
        resources_dir: Path):
    result_dir = work_dir / 'result'
    result_dir.mkdir(exist_ok=True)

    params = {}
    params['scene_file'] = resources_dir / 'bmw27_cpu.blend'
    params['frames'] = [1]
    params['output_format'] = 'PNG'
    params['resolution'] = [200, 100]
    params['crops'] = [{
        'outfilebasename': 'result',
        'borders_x': [0.0, 1.0],
        'borders_y': [0.0, 1.0],
    }]
    params['use_compositing'] = False
    params['samples'] = 0
    start_time = time.time()
    blender_render.render(
        params,
        {
            "WORK_DIR": str(work_dir),
            "OUTPUT_DIR": str(result_dir),
        },
    )
    print(time.time() - start_time)
