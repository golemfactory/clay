import click
import statistics
import math
import random
import matplotlib.pyplot as plt


@click.command()
@click.argument("results")
@click.option("--probs", default=0)
@click.option("--name", default="Rendering time")
@click.option("--plot/--no-plot", default=True)
@click.option("--repeat_prob/--no-repeat_prob", default=False)
def run_stats(results, probs, name, plot, repeat_prob):
    times = []
    with open(results) as f:
        for line in f:
            result = line.split(" ")[2]
            times.append(__str_to_time(result))

    n = len(times)
    if probs == 0:
        probs = len(times)
    times_p = random.sample(times, probs)
    mean = statistics.mean(times_p)
    print "PROBS: {}".format(len(times_p))
    print "ESTM_TIME: {} ({})".format(__time_to_str(n*mean), n*mean)
    print "MEAN: {} ({})".format(__time_to_str(mean), mean)
    print "DEVIATION: {} ({})".format(__time_to_str(statistics.stdev(times_p)), statistics.stdev(times_p))
    print "VARIANCE: {} ({})".format(__time_to_str(statistics.variance(times_p)), statistics.variance(times_p))
    print "MAX_VAL: {} ({})".format(__time_to_str(max(times_p)), max(times_p))
    print "MIN_VAL: {} ({})".format(__time_to_str(min(times_p)), min(times_p))

    if repeat_prob:
        estm_times = []
        for i in range(100):
            times_p = random.sample(times, probs)
            estm_times.append(statistics.mean(times_p))
        print "#######################"
        mean = statistics.mean(estm_times)
        std_dev = statistics.stdev(estm_times)
        min_ = min(estm_times)
        max_ = max(estm_times)
        print "100 PROBS ESTM_TIME: {} ({})".format(__time_to_str(n*mean), n*mean)
        print "100 PROBS MEAN: {} ({})".format(__time_to_str(mean), mean)
        print "100 PROBS DEVIATION: {} ({})".format(__time_to_str(std_dev), std_dev)
        print "100 PROBS MAX: {} ({})".format(__time_to_str(max_*n), max_*n)
        print "100 PROBS MIN: {} ({})".format(__time_to_str(min_*n), min_*n)

    if plot:
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
