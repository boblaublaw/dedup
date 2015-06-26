#!/usr/bin/env python

import hashlib
import os
import sys

class HashMap:
    def __init__(self):
        self.m = {}

    def addEntry(self, hashval, entry):
        if hashval in self.m:
            self.m[hashval].append(entry)
        else:
            self.m[hashval] = [ entry ]

    def display(self):
        for hashval, list in self.m.iteritems():
            for entry in list:
                entry.display(False, False)

    def delete(self, entry):
        # mark this entry (and any children) as deleted
        entry.delete()

        # remove the entry from the hashmap
        list=self.m[entry.hashval]
        newlist = []
        for e in list:
            if e != entry:
                newlist.append(e)

        # if there are no more entries for this hashval, remove
        # it from the dictionary m
        if len(newlist):
            self.m[entry.hashval] = newlist
        else:
            del self.m[entry.hashval]

        # also remove all the deleted children from the hashmap
        self.prune()

    def prune(self):
        # removes deleted objects from the hashMap
        for hashval, list in self.m.iteritems():
            newlist=[]
            for entry in list:
                if not entry.deleted:
                    newlist.append(entry)
            self.m[hashval]=newlist

class DirObj():
    def __init__(self, name, parent=None):
        self.name=name
        self.files={}
        self.deleted=False
        self.subdirs={}
        self.parent=parent
        ancestry=self.get_lineage()
        self.pathname='/'.join(ancestry) 
        self.depth=len(ancestry)

    def get_lineage(self):
        if self.parent == None:
            return self.name.split('/')
        ancestry=self.parent.get_lineage()
        ancestry.append(self.name)
        return ancestry

    def max_depth(self):
        md=self.depth
        if len(self.subdirs.keys()):
            for name, entry in self.subdirs.iteritems():
                td = entry.max_depth()
                if td > md:
                    md=td
            return md
        elif len(self.files.keys()):
            return md + 1
        else:
            return md
    
    def display(self, contents=False, recurse=False):
        if recurse:
            for name, entry in self.subdirs.iteritems():
                entry.display(contents, recurse)
        if contents:
            for name, entry in self.files.iteritems():
                entry.display(contents, recurse);
        print 'Directory\t' + str(self.deleted) + '\t' + str(self.depth) + '\t' + self.hexdigest + ' ' + self.pathname 

    def place_dir(self, inputDirName):
        #print "looking to place " +  inputDirName + " in " + self.name
        inputDirList=inputDirName.split('/')
        nameList=self.name.split('/')

        while (len(inputDirList) and len(nameList)):
            x=inputDirList.pop(0)
            y=nameList.pop(0)
            if x != y:
                print x + ' and ' + y + ' do not match'
                raise LookupError
        
        if len(inputDirList) == 0:
            return self

        nextDirName=inputDirList[0]
        if nextDirName in self.subdirs:
            #print "found " + nextDirName + " in " + self.name
            return self.subdirs[nextDirName].place_dir('/'.join(inputDirList))

        #print "did not find " + nextDirName + " in " + self.name
        nextDir=DirObj(nextDirName, self)
        self.subdirs[nextDirName]=nextDir
        return nextDir.place_dir('/'.join(inputDirList))

    def place_file(self, fileName, parent = None):
        self.files[fileName]=FileObj(fileName, self)

    def delete(self):
        self.deleted=True
        for name, d in self.subdirs.iteritems:
            d.delete()
        for name, f in self.files.iteritems:
            f.delete()
    
    def close(self):
        digests=[]
        for filename, file_entry in self.files.iteritems():
            digests.append(file_entry.hexdigest)
        for dirname, dir_entry in self.subdirs.iteritems():
            digests.append(dir_entry.hexdigest)
        digests.sort()
        sha1 = hashlib.sha1()
        for d in digests:
            sha1.update(d)
        self.hexdigest=sha1.hexdigest()
        h.addEntry(self.hexdigest, self)
    
class FileObj():
    def __init__(self, name, parent=None):
        self.name=name;
        self.parent=parent
        self.deleted=False
        ancestry=self.parent.get_lineage()
        if self.parent != None:
            self.pathname='/'.join(ancestry) + '/' + self.name
        else:
            self.pathname=self.name
        self.depth=len(ancestry) + 1

        # open and read the file
        sha1 = hashlib.sha1()
        with open(self.pathname, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
        self.hexdigest=sha1.hexdigest()
        h.addEntry(self.hexdigest, self)

    def delete(self):
        self.deleted=True

    def display(self, contents=False, recurse=False):
        print 'File\t\t' + str(self.deleted) + '\t' + str(self.depth) + '\t' + self.hexdigest + ' ' + self.pathname # + ' ' + str(os.stat(self.pathname))

topLevelList = {}
BUF_SIZE = 65536  
h=HashMap()
sys.argv.pop(0)
maxDepth=1      # i assume at least one file or dir here
# walk argv adding files and directories
for entry in sys.argv:
    # TODO strip trailing slashes
    # TODO check for special files (sockets)
    if os.path.isfile(entry):
        topLevelList[entry]=FileObj(entry)
    elif os.path.isdir(entry):
        topDirEntry=DirObj(entry)
        topLevelList[entry]=topDirEntry
        for dirName, subdirList, fileList in os.walk(entry, topdown=False):
            dirEntry=topDirEntry.place_dir(dirName)
            for fname in fileList:
                dirEntry.place_file(fname)
            dirEntry.close()
        td=topDirEntry.max_depth()
        if maxDepth < td:
            maxDepth=td
    else:
        print "I don't know what this is" + entry

h.display()
print 'max depth is ' + str(maxDepth)
