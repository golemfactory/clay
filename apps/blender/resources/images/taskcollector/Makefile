UNAME := $(shell uname)

CXX=g++
LDFLAGS=-lfreeimage

CXXFLAGS=-std=c++14 -Wall -Wextra -O2 -g

.PHONY: all clean

all: taskcollector

clean:
	rm taskcollector

taskcollector: TaskCollector.cpp
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
