#!/usr/bin/env python

import fileinput
import hashlib

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
    def __init__(self, name=None, parent=None):
        self.files={}
        self.subdirs={}
        self.name=name
        self.parent=parent

    def placeFile(self, f):
        if len(f.ancestry):
            oldest=f.ancestry.pop(0)
            if (oldest not in self.subdirs):
                self.subdirs[oldest]=dirobj(oldest, self)
            self.subdirs[oldest].placeFile(f)
        else:
            self.files[f.name]=f

    def getLineage(self):
        if self.parent == None:
            return [ self.name ]
        ancestry=self.parent.getLineage()
        ancestry.append(self.name)
        return ancestry

    def display(self):
        for name, f in self.files.iteritems():
            print f.dirname + '/' + f.name + " with hash " + f.hashval
        for name, d in self.subdirs.iteritems():
            d.display()
        print '/'.join(self.getLineage()) + " with hash " + self.hashval

    def computeDigests(self):
        digests=[]
        for name, f in self.files.iteritems():
            digests.append(f.hashval)
        for name, d in self.subdirs.iteritems():
            digests.append(d.computeDigests())

        digests.sort()
        h=hashlib.new("sha1")
        for d in digests:
            #print "adding digest " + d 
            h.update(d)
        self.hashval=h.hexdigest()
        #print "directory " + '/'.join(self.getLineage()) + " hashes to " + hexdigest
        return self.hashval
        

root=dirobj(".")

for line in fileinput.input():
    fields = line.split('|');
    hashtype=fields[0]
    hashval=fields[1]
    pathname=fields[2].rstrip()
    f=fileobj(hashtype, hashval, pathname)
    root.placeFile(f)
      
if len(root.subdirs) == 1:
    for name, d in root.subdirs.iteritems():
        root=d

root.computeDigests()
root.display()

