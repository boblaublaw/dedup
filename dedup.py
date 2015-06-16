#!/usr/bin/env python

import fileinput

class fileobj:
    def __init__(self, hashtype, hashval, pathname):
        parts=pathname.split("/")
        self.name=parts.pop()
        self.ancestry=parts
        self.dirname='/'.join(parts)
        #print "created a file " + self.name + " in dir " + self.dirname
        self.hashval=hashval
        self.hashtype=hashtype

class dirobj:
    def __init__(self, name=None):
        self.files={}
        self.subdirs={}
        self.name=name

    def placeFile(self, f):
        if len(f.ancestry):
            oldest=f.ancestry.pop(0)
            if (oldest not in self.subdirs):
                self.subdirs[oldest]=dirobj(oldest)
            self.subdirs[oldest].placeFile(f)
        else:
            self.files[f.name]=f

    def traverse(self):
        for name, f in self.files.iteritems():
            print f.dirname + '/' + f.name
        for name, d in self.subdirs.iteritems():
            d.traverse()

root=dirobj(".")

for line in fileinput.input():
    fields = line.split('|');
    hashtype=fields[0]
    hashval=fields[1]
    pathname=fields[2].rstrip()

    f=fileobj(hashtype, hashval, pathname)
    root.placeFile(f)
       
root.traverse()

