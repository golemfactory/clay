
import sys

sys.path.append('../src/')
sys.path.append('../src/core')
sys.path.append('../src/vm')
sys.path.append('../src/task')
sys.path.append('../src/task/resource')
sys.path.append('../src/network')
sys.path.append('../src/manager')
sys.path.append('../src/manager/server')
sys.path.append('../src/manager/client')
sys.path.append('../testtasks/minilight/src')
sys.path.append('../testtasks/pbrt')
sys.path.append('../tools/')

from UiGen import genUiFiles

genUiFiles( "./../examples/gnr/ui" )

def main():
    pass

main()