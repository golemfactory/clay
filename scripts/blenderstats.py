import click
import statistics
import math
import random
import matplotlib.pyplot as plt


@click.command()
@click.argument("results")
@click.option("--probs", default=0)
@click.option("--name", default="Rendering time")
def run_stats(results, probs, name):
    times = []
    with open(results) as f:
        for line in f:
            result = line.split(" ")[2]
            times.append(__str_to_time(result))

    n = len(times)
    if probs == 0:
        probs = len(times)
    times = random.sample(times, probs)
    mean = statistics.mean(times)
    print "PROBS: {}".format(len(times))
    print "ESTM_TIME: {} ({})".format(__time_to_str(n*mean), n*mean)
    print "MEAN: {} ({})".format(__time_to_str(mean), mean)
    print "DEVIATION: {} ({})".format(__time_to_str(statistics.stdev(times)), statistics.stdev(times))
    print "VARIANCE: {} ({})".format(__time_to_str(statistics.variance(times)), statistics.variance(times))
    print "MAX_VAL: {} ({})".format(__time_to_str(max(times)), max(times))
    print "MIN_VAL: {} ({})".format(__time_to_str(min(times)), min(times))
    plt.hist(times)
    plt.title(name)
    plt.xlabel("time in sec")
    plt.ylabel("frequency")
    plt.show()


def __str_to_time(result):
    time_ = result.split(":")
    if len(time_) == 2:
        return float(time_[0])*60 + float(time_[1])
    else:
        return float(time_[0])*60*60 + float(time_[1])*60*60 + float(time_[2])


def __time_to_str(time_):
    hours = int(math.floor(time_ / 3600))
    minutes = int(math.floor((time_ - 3600 * hours) / 60))
    seconds = time_ % 60
    if hours > 0:
        return "{0:02.0f}:{1:02.0f}:{2:08.5f}".format(hours, minutes, seconds)
    else:
        return "{0:02.0f}:{1:08.5f}".format(minutes, seconds)


if __name__ == "__main__":
    run_stats()
