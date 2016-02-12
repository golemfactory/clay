import click
import re


@click.command()
@click.argument("file_name")
@click.option("--results", default="result.txt")
def parse_file(results, file_name):
    times = []
    with open(file_name) as f:
        for line in f:
            pattern = re.search("^ Time:", line)
            if pattern:
                times.append(line)
    with open(results, 'w') as f:
        for line in times:
            f.write(line)


if __name__ == "__main__":
    parse_file()
