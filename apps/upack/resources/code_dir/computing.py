import os
import subprocess


def run_upack_task(dst):
    cmds = '''
    runcod etanol.con.s
    runmk out.tp
    runpp s etanol none lj
    cp cart.out cart.in
    list=(180 60 180 300 60 -60); for ((i=0;i<${#list[@]};i++));do line=$(($i+1)); sed -i "${line}s/$/ ${list[$i]}/" cart.in; done
    runpp s etanol none lj
    runpp s etanol cor.001 lj
    runcod etanol.con.a opls
    runmk out.tp opls
    '''.split('\n')

    for cmd in cmds:
        subprocess.call(cmd, shell=True, env=os.environ.copy(), cwd=dst, executable='/bin/bash')