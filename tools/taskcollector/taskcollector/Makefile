CXX=g++
LDFLAGS=-static -L /usr/lib/libfreeimage.so -lfreeimage
CXXFLAGS=-Wall -O2

taskcolletor: taskcollector.cpp
    $(CXX) $(CXXFLAGS) $< $(LDFLAGS) -o $@