#!/usr/bin/env python

import hashlib
import os
import sys
 
BUF_SIZE = 65536  

# Set the directory you want to start from

topLevelList = {}

class dirObj():
    def __init__(self, name, parent=None):
        self.name=name
        self.files={}
        self.subdirs={}
        self.parent=parent
        self.pathname = '/'.join(self.getLineage()) 

    def getLineage(self):
        if self.parent == None:
            return [ self.name ]
        ancestry=self.parent.getLineage()
        ancestry.append(self.name)
        return ancestry
    
    def display(self):
        for name, entry in self.subdirs.iteritems():
            entry.display()
        for name, entry in self.files.iteritems():
            entry.display();
        print 'Directory\t' + self.hexdigest + ' ' + self.pathname 

    def placeDir(self, dirName):
        #print "looking to place " +  dirName + " in " + self.name
        dirList=dirName.split('/')
        if dirList.pop(0) != self.name:
            raise LookupError
        
        if len(dirList) == 0:
            return self

        nextDirName=dirList[0]
        if nextDirName in self.subdirs:
            #print "found " + nextDirName + " in " + self.name
            return self.subdirs[nextDirName].placeDir('/'.join(dirList))

        #print "did not find " + nextDirName + " in " + self.name
        nextDir=dirObj(nextDirName, self)
        self.subdirs[nextDirName]=nextDir
        return nextDir.placeDir('/'.join(dirList))

    def placeFile(self, fileName, parent = None):
        self.files[fileName]=fileObj(fileName, self)
    
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
    
class fileObj():
    def __init__(self, name, parent=None):
        self.name=name;
        self.parent=parent
        if self.parent != None:
            self.pathname='/'.join(self.parent.getLineage()) + '/' + self.name
        else:
            self.pathname=self.name

        # open and read the file
        sha1 = hashlib.sha1()
        with open(self.pathname, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
        self.hexdigest=sha1.hexdigest()
    
    def display(self):
        print 'File\t\t' + self.hexdigest + ' ' + self.pathname # + ' ' + str(os.stat(self.pathname))

sys.argv.pop(0)

for entry in sys.argv:
    if os.path.isfile(entry):
        #print 'Found a file:\t\t' + entry
        topLevelList[entry]=(fileObj(entry))
    elif os.path.isdir(entry):
        topDirEntry=dirObj(entry)
        topLevelList[entry]=topDirEntry
        for dirName, subdirList, fileList in os.walk(entry, topdown=False):
            dirEntry=topDirEntry.placeDir(dirName)
            for fname in fileList:
                #print('\t\t\t%s/%s' % (dirName, fname))
                dirEntry.placeFile(fname)
            #print('Found directory:\t%s' % dirName)
            dirEntry.close()
    else:
        print "I don't know what this is" + entry

print
for name, entry in topLevelList.iteritems():
    entry.display()

