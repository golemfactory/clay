from os.path import abspath, dirname, isfile, join
from subprocess import check_call, Popen, PIPE
from sys import platform


class TaskCollectorBuilder:
    """ Class for building Task Collector """

    def __init__(self):
        self.golem_path = dirname(abspath(dirname(__file__)))
        self.task_collector_path = join(self.golem_path, 'apps/rendering/resources/taskcollector/')
        self.build_path = join(self.task_collector_path, 'Release/taskcollector')

    def build(self):
        """
        Try to build taskcollector
        :return: None if taskcollector is built. Error message otherwise
        """
        if platform.startswith('win') or platform.startswith('nt'):
            return self.__build_on_windows()
        elif platform.startswith('linux') or platform.startswith("darwin"):
            return self.__build_on_unix()
        else:
            return \
                """
                ***************************************************************
                Cannot build TaskCollector
                Unsupported platform: {}
                ***************************************************************
                """.format(platform)

    def __build_on_windows(self):
        """ Check if taskcollector exists """
        # @todo check how to call cl.exe from cmd and try to build
        if not isfile("{}.exe".format(self.build_path)):
            return \
                """
                ***************************************************************
                {}.exe not found!
                ***************************************************************
                """.format(self.build_path)
        return None

    def __build_on_unix(self):
        """
        Check if Task Collector has been already built. If not, try to build it
        :return: None if taskcollector is built. Error message otherwise
        """
        if isfile(self.build_path):
            print "Task Collector already built"
            return None
        print "Try to build TaskCollector"
        try:
            check_call(['make', '--version'])
            p = Popen(['make', '-C', self.task_collector_path], stdout=PIPE, stderr=PIPE)
            _, error_msg = p.communicate()
        except OSError as ex:
            return ex.message
        if not isfile(self.build_path):
            return \
                """
                ***************************************************************
                Building TaskCollector failed
                {}
                ***************************************************************
                """.format(error_msg)
        return None
