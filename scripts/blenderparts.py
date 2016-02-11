import subprocess
import os
import tempfile
import shutil
import click
import appdirs

from golem.core.common import get_golem_path
from gnr.task.scenefileeditor import regenerate_blender_crop_file


def make_script(res_x, res_y, x0=0.0, x1=1.0, y0=0.0, y1=1.0, tmp_dir=None):
    script_path = os.path.join(get_golem_path(), "gnr", "task", "scripts", "blendercrop.py")
    with open(script_path) as f:
        script_src = f.read()
    script_src = regenerate_blender_crop_file(script_src, res_x, res_y, x0, x1, y0, y1)
    new_script = tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False)
    with open(new_script.name, 'w') as f:
        f.write(script_src)
    return new_script.name


def get_blender_cmd(scene_file, script, output_path, part=1):
    return format_blender_render_cmd(["blender", "-b"], scene_file, script, output_path, part)


def format_blender_render_cmd(app_cmd, scene_file, script, output_path, part=1):
    cmd = [scene_file, "-o", os.path.join(output_path, "result_###_{}".format(part)),
           "-P", script, "-f", "1"]
    return app_cmd + cmd


def get_docker_blender_cmd(scene_file, script, output_path, part=1, docker_name="ikester/blender",
                           working_dir="scene"):
    cmd = ["docker", "run", "-v", "{}:/{}".format(os.path.dirname(scene_file), working_dir), docker_name]
    scene_file = "/{}/{}".format(working_dir, os.path.basename(scene_file))
    script = "/{}/{}/{}".format(working_dir, os.path.basename(os.path.dirname(script)), os.path.basename(script))
    return format_blender_render_cmd(cmd, scene_file, script, output_path, part)


@click.command()
@click.argument('scene')
@click.option('--result', '-r', default="result.txt")
@click.option('--output', '-o', default=appdirs.user_data_dir('golem'))
@click.option('--res_x', default=800)
@click.option('--res_y', default=600)
@click.option('-n', default=1)
@click.option('-m', default=1)
@click.option('--docker/--no-docker', default=False)
def run_blender(scene, result, output, n, m, res_x, res_y, docker):
    print "scene: {}".format(scene)
    print "result: {}".format(result)
    print "output: {}".format(output)
    print "res {}:{}".format(res_x, res_y)
    print "n: {}".format(n)
    print "m: {}".format(m)
    print "using docker: {}".format(docker)
    try:
        results = []
        cnt = 0
        script = None
        if docker:
            tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(scene), prefix='golem')
        else:
            tmp_dir = tempfile.mkdtemp(prefix='golem')
        for i in [x * 1.0/n for x in range(n)]:
            for j in [x * 1.0/m for x in range(m)]:
                script = make_script(res_x, res_y, i, i + 1.0/n, j, j + 1.0/m, tmp_dir)
                cnt += 1
                print "computing part {}".format(cnt)
                if docker:
                    cmd = get_docker_blender_cmd(scene, script, output_path=output, part=cnt)
                else:
                    cmd = get_blender_cmd(scene, script, output_path=output, part=cnt)
                pc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out, err = pc.communicate()
                pc.wait()
                results.append(out.splitlines()[-4])

        with open(result, 'w') as f:
            for res in results:
                f.writelines("%s\n" % res)
    finally:
        if script:
            shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    run_blender()

