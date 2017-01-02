import time

from golem.core.variables import BREAK_TIME, ROUND_TIME, END_ROUND_TIME, STAGE_TIME


class TimeManager:
    def __init__(self, break_time=BREAK_TIME, round_time=ROUND_TIME, end_round_time=END_ROUND_TIME,
                 stage_time=STAGE_TIME):
        self.break_time = break_time
        self.round_time = round_time
        self.end_round_time = end_round_time
        self.stage_time = stage_time

    def __sum_time(self):
        return self.round_time + self.break_time + self.end_round_time

    def __time_mod(self):
        return time.time() % self.__sum_time()

    def sec_to_end_round(self):
        tm = self.round_time - self.__time_mod()
        return tm if tm >= 0 else self.__sum_time() + tm

    def sec_to_round(self):
        return self.__sum_time() - self.__time_mod()

    def sec_to_break(self):
        tm = self.round_time + self.end_round_time - self.__time_mod()
        return tm if tm >= 0 else self.__sum_time() + tm

    def sec_to_new_stage(self):
        return self.stage_time - time.time() % self.stage_time
