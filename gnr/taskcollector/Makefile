CXX=g++-5
LDFLAGS=-Bstatic -L /usr/lib/libfreeimage.so -lfreeimage
CXXFLAGS=-std=c++14 -Wall -Wextra -O2

Release/taskcollector: TaskCollector.cpp
	$(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@
