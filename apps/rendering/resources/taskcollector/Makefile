UNAME := $(shell uname)

ifeq ($(UNAME), Darwin)
	CXX=g++
	LDFLAGS=-lfreeimage
else
	CXX=g++-5
	LDFLAGS=-lfreeimage
endif

CXXFLAGS=-std=c++14 -Wall -Wextra -O2 -g

.PHONY: all clean

all: Release/taskcollector

clean:
	rm -f Release/taskcollector

Release/taskcollector: TaskCollector.cpp
	mkdir -p Release
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
