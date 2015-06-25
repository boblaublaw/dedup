#!/usr/bin/env python

import hashlib
import os
 
# Set the directory you want to start from

inputList = [ 'work_usb', 'test', 'dedup.py' ] 
topLevelList = {}

class dirObj():
    def __init__(self, pathname):
        self.pathname=pathname
        self.files={}
        self.subdirs={}

    def placeDir(self, dirName):
        print "looking to place " +  dirName + " in " + self.pathname
        dirList=dirName.split('/')
        if dirList.pop(0) != self.pathname:
            raise LookupError
        
        if len(dirList) == 0:
            return self

        nextDirName=dirList[0]
        if nextDirName in self.subdirs:
            print "found " + nextDirName + " in " + self.pathname
            return self.subdirs[nextDirName].placeDir('/'.join(dirList))

        print "did not find " + nextDirName + " in " + self.pathname
        nextDir=dirObj(nextDirName)
        self.subdirs[nextDirName]=nextDir
        return nextDir.placeDir('/'.join(dirList))

    def placeFile(self, fileName):
        self.files[fileName]=fileObj(fileName)
    
class fileObj():
    def __init__(self, name):
        self.name=name;
    
for entry in inputList: 
    if os.path.isfile(entry):
        print 'Found a file:\t\t' + entry
        topLevelList[entry]=(fileObj(entry))
    elif os.path.isdir(entry):
        topDirEntry=dirObj(entry)
        topLevelList[entry]=topDirEntry
        for dirName, subdirList, fileList in os.walk(entry, topdown=False):
            dirEntry=topDirEntry.placeDir(dirName)
            for fname in fileList:
                print('\t\t\t%s/%s' % (dirName, fname))
                #dirEntry.placeFile(fname)
            print('Found directory:\t%s' % dirName)
    else:
        print "I don't know what this is" + entry



