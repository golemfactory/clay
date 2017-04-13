UNAME := $(shell uname)

ifeq ($(UNAME), Darwin)
	CXX=g++
	LDFLAGS=-lfreeimage
else
	LFREEIMAGE=/usr/lib/x86_64-linux-gnu/libfreeimage.so

	ifneq ($(shell test -e $(LFREEIMAGE) && echo -n yes),yes)
		LFREEIMAGE=/usr/lib/libfreeimage.so
	endif

	CXX=g++-5
	LDFLAGS=-Bstatic -L $(LFREEIMAGE) -lfreeimage
endif

CXXFLAGS=-std=c++14 -Wall -Wextra -O2 -g

.PHONY: all clean

all: Release/taskcollector

clean:
	rm -f Release/taskcollector

Release/taskcollector: TaskCollector.cpp
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
