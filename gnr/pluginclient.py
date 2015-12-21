import zerorpc
import sys
import getopt


def usage():
    print "--task <filename> [--port <port>]"


def main(argv):
    try:
        opts, args = getopt.getopt(argv, "ht:p:", ["help", "task=", "port="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    c = zerorpc.Client()
    port = 1111
    for opt, arg in opts:
        if opt in ("-p", "--port"):
            port = arg
    c.connect("tcp://127.0.0.1:{}".format(port))

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-t", "--task"):
            c.add_task(arg)

if __name__ == "__main__":
    main(sys.argv[1:])