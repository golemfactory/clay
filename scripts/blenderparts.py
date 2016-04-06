import subprocess
import os
import posixpath
import tempfile
import shutil
import click
import appdirs
import re

from golem.core.common import is_windows


def make_script(res_x, res_y, x0=0.0, x1=1.0, y0=0.0, y1=1.0, tmp_dir=None, output_path=None, n=None, m=None):
    if output_path:
        output_path = '"' + output_path + '/res_{}.png".format(cnt)'
    print output_path
    script_path = os.path.join(os.path.dirname(__file__), "blendercrop.py")
    with open(script_path) as f:
        script_src = f.read()
    script_src = regenerate_blender_crop_file(script_src, res_x, res_y, x0, x1, y0, y1, output_path, n, m)
    new_script = tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False)
    with open(new_script.name, 'w') as f:
        f.write(script_src)
    return new_script.name


def get_blender_cmd(scene_file, script, output_path, part=1, frame=1):
    if output_path:
        output_path = os.path.join(output_path, "result_###_{}".format(part))
    return format_blender_render_cmd(["blender", "-b"], scene_file, script, output_path, frame)


def format_blender_render_cmd(app_cmd, scene_file, script, output_path, frame=1):
    cmd = [scene_file, "-P", script]
    if output_path:
        cmd += ["-o", output_path]
    if frame:
        cmd += ["-f", str(frame)]
    return app_cmd + cmd


def change_to_linux_path(path_):
    if is_windows():
        path_ = path_.replace("\\", "/")
        path_ = path_.split(":")
        if len(path_) > 1:
            return "/" + path_[0].lower() + path_[1]
        return path_[0]
    else:
        return path_


def get_docker_blender_cmd(scene_file, script, output_path, part=1, docker_name="ikester/blender",
                           working_dir="scene", frame=1):
    scene_file = change_to_linux_path(scene_file)
    cmd = ["docker", "run", "-v", "{}:/{}".format(os.path.dirname(scene_file), working_dir), docker_name]
    scene_file = "/{}/{}".format(working_dir, os.path.basename(scene_file))
    script = "/{}/{}/{}".format(working_dir, os.path.basename(os.path.dirname(script)), os.path.basename(script))
    if output_path:
        output_path = posixpath.join(output_path, "result_###_{}".format(part))
    return format_blender_render_cmd(cmd, scene_file, script, output_path, frame)


@click.command()
@click.argument('scene')
@click.option('--result', '-r', default="result.txt")
@click.option('--output', '-o', default=appdirs.user_data_dir('golem'))
@click.option('--res_x', default=800)
@click.option('--res_y', default=600)
@click.option('-n', default=1)
@click.option('-m', default=1)
@click.option('--docker/--no-docker', default=False)
@click.option('--inner/--no-inner', default=False)
def run_blender(scene, result, output, n, m, res_x, res_y, docker, inner):
    print "scene: {}".format(scene)
    print "result: {}".format(result)
    print "output: {}".format(output)
    print "res {}:{}".format(res_x, res_y)
    print "n: {}".format(n)
    print "m: {}".format(m)
    print "using docker: {}".format(docker)
    print "using inner: {}".format(inner)
    try:
        results = []
        if docker:
            tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(scene), prefix='golem-blender-')
        else:
            tmp_dir = tempfile.mkdtemp(prefix='golem-blender-')
        if inner:

            make_inner_blend(n, m, res_x, res_y, scene, docker, tmp_dir, output, results)
        else:
            make_outer_blend(n, m, res_x, res_y, scene, docker, tmp_dir, output, results)

        with open(result, 'w') as f:
            for res in results:
                f.writelines("%s\n" % res)
    finally:
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)


def make_inner_blend(n, m, res_x, res_y, scene, docker, tmp_dir, output, results):

    if docker:
        output = "/scene"
    script = make_script(res_x, res_y, None, None, None, None, tmp_dir, output, n, m)
    if docker:
        cmd = get_docker_blender_cmd(scene, script, output_path=None, frame=None)
    else:
        cmd = get_blender_cmd(scene, script, output_path=None, frame=None)
    out, err = run_cmd(cmd)
    results += out.splitlines()


def make_outer_blend(n, m, res_x, res_y, scene, docker, tmp_dir, output, results):
    cnt = 0
    for i in [x * 1.0/n for x in range(n)]:
        for j in [x * 1.0/m for x in range(m)]:
            script = make_script(res_x, res_y, i, i + 1.0/n, j, j + 1.0/m, tmp_dir, None, n=0, m=0)
            cnt += 1
            print "computing part {}".format(cnt)
            if docker:
                cmd = get_docker_blender_cmd(scene, script, output_path=output, part=cnt)
            else:
                cmd = get_blender_cmd(scene, script, output_path=output, part=cnt)
            out, err = run_cmd(cmd)
            results.append(out.splitlines()[-4])

def run_cmd(cmd):
    print cmd
    pc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = pc.communicate()
    pc.wait()
    return out, err


def regenerate_blender_crop_file(crop_file_src, xres, yres, min_x=None, max_x=None, min_y=None, max_y=None,
                                      filepath=None, n=None, m=None):
    out = ""

    for l in crop_file_src.splitlines():
        line = re.sub(r'(resolution_x\s*=)(\s*\d*\s*)', r'\1 {}'.format(xres), l)
        line = re.sub(r'(resolution_y\s*=)(\s*\d*\s*)', r'\1 {}'.format(yres), line)
        if max_x:
            line = re.sub(r'(border_max_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_x), line)
        if min_x:
            line = re.sub(r'(border_min_x\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_x), line)
        if min_y:
            line = re.sub(r'(border_min_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(min_y), line)
        if max_y:
            line = re.sub(r'(border_max_y\s*=)(\s*\d*.\d*\s*)', r'\1 {}'.format(max_y), line)
        if filepath:
            newline = re.sub(r'(filepath\s*=)(.*)', r'\1 {}'.format(""), line)
            if line != newline:
                line = newline + filepath
        if n is not None:
            line = re.sub(r'(\s*n\s*=)(\s*\d*\s*)', r'\1 {}'.format(n), line)
        if m is not None:
            line = re.sub(r'(\s*m\s*=)(\s*\d*\s*)', r'\1 {}'.format(m), line)
        out += line + "\n"

    return out


if __name__ == "__main__":
    run_blender()
