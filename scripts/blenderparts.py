import subprocess
import os
import tempfile
import shutil
import click
import appdirs

from golem.core.common import get_golem_path
from gnr.task.scenefileeditor import regenerate_blender_crop_file


def make_script(res_x, res_y, x0=0.0, x1=1.0, y0=0.0, y1=1.0):
    path = tempfile.mkdtemp(prefix='golem')
    script_path = os.path.join(get_golem_path(), "gnr", "task", "scripts", "blendercrop.py")
    with open(script_path) as f:
        script_src = f.read()
    script_src = regenerate_blender_crop_file(script_src, res_x, res_y, x0, x1, y0, y1)
    new_script = tempfile.NamedTemporaryFile(dir=path, delete=False)
    with open(new_script.name, 'w') as f:
        f.write(script_src)
    return new_script.name


def format_blender_render_cmd(scene_file, script, output_path, part=1, app_name="blender"):
    cmd = [app_name, "-b", scene_file, "-o", os.path.join(output_path, "result_###_{}".format(part)),
           "-P", script, "-f", "1"]

    return cmd


@click.command()
@click.argument('scene')
@click.option('--result', '-r', default="result.txt")
@click.option('--output', '-o', default=appdirs.user_data_dir('golem'))
@click.option('--res_x', default=800)
@click.option('--res_y', default=600)
@click.option('-n', default=1)
def run_blender(scene, result, output, n, res_x, res_y):
    print "scene: {}".format(scene)
    print "result: {}".format(result)
    print "output: {}".format(output)
    print "res {}:{}".format(res_x, res_y)
    print "n: {}".format(n)
    try:
        results = []
        cnt = 0
        script = None
        for i in [x * 1.0/n for x in range(n)]:
            for j in [x * 1.0/n for x in range(n)]:
                script = make_script(res_x, res_y, i, i + 1.0/n, j, j + 1.0/n)
                cnt += 1
                print "computing part {}".format(cnt)
                cmd = format_blender_render_cmd(scene, script, output_path=output, part=cnt)
                pc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = pc.communicate()
                pc.wait()
                results.append(out.splitlines()[-4])

        with open(result, 'w') as f:
            for res in results:
                f.writelines("%s\n" % res)
    finally:
        if script:
            shutil.rmtree(os.path.dirname(script))


if __name__ == "__main__":
    run_blender()

