CXX=g++-5
LDFLAGS=-static -L /usr/lib/libfreeimage.so -lfreeimage -g
CXXFLAGS=-std=c++14 -Wall -Wextra -O2

Release/taskcollector: TaskCollector.cpp
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
