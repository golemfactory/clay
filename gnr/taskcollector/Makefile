CXX=g++-5
LDFLAGS=-static -L /usr/lib/libfreeimage.so -lfreeimage
CXXFLAGS=-std=c++14 -Wall -Wextra -O2 -g

.PHONY: all clean

all: Release/taskcollector

clean:
	rm -f Release/taskcollector

Release/taskcollector: TaskCollector.cpp
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
