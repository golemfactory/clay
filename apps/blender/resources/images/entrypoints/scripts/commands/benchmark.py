from pathlib import Path
import time

from ..render_tools import blender_render


def benchmark(
        work_dir: Path,
        resources_dir: Path):
    result_dir = work_dir / 'result'
    result_dir.mkdir()

    params = {
        'scene_file': resources_dir / 'bmw27_cpu.blend',
        'frames': [1],
        'output_format': 'png',
        'resolution': [200, 100],
        'crops': [{
            'outfilebasename': 'result',
            'borders_x': [0.0, 1.0],
            'borders_y': [0.0, 1.0],
        }],
        'use_compositing': False,
        'samples': 0,
    }
    start_time = time.time()
    blender_render.render(
        params,
        {
            "WORK_DIR": str(work_dir),
            "OUTPUT_DIR": str(result_dir),
        },
    )
    print(time.time() - start_time)
