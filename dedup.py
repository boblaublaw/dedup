#!/usr/bin/env python

import hashlib
import os
import sys
import stat

def issocket(path):
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

def resolve_candidates(candidates, currentDepth=None):
    depthMap={}
    losers = []
    for candidate in candidates:
        if currentDepth != None and candidate.depth > currentDepth:
            continue
        if candidate.depth not in depthMap:
            depthMap[candidate.depth] = candidate
        else:
            incumbent = depthMap[candidate.depth]
            if len(incumbent.name) > len(candidate.name):
                depthMap[candidate.depth] = candidate
            
    k=depthMap.keys()
    if len(k) == 0:
        return None, losers

    k.sort()
    md=k.pop(0)
    winner=depthMap[md]
    for candidate in candidates:
        if candidate != winner:
            losers.append(candidate)
    return winner, losers
        
class HashMap:
    def __init__(self):
        self.purge()

    def purge(self):
        self.m = {}

    def addEntry(self, entry):
        # hash digest value
        hv=entry.hexdigest
        
        if hv in self.m:
            self.m[hv].append(entry)
        else:
            self.m[hv] = [ entry ]

    def display(self):
        for hashval, list in self.m.iteritems():
            for entry in list:
                entry.display(False, False)

    def delete(self, entry):
        # mark this entry (and any children) as deleted
        entry.delete()

        # remove the entry from the hashmap
        list=self.m[entry.hexdigest]
        newlist = []
        for e in list:
            if e != entry:
                newlist.append(e)

        # if there are no more entries for this hashval, remove
        # it from the dictionary m
        if len(newlist):
            self.m[entry.hexdigest] = newlist
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

    def resolve(self, maxDepth):
        #print 'before'
        #self.display() 
        #print
        # no need to resolve uniques, so remove them from the dict 
        deleteList=[]
        for hashval, list in self.m.iteritems():
            if len(list) == 1:
                deleteList.append(hashval)
        for e in deleteList:
            del self.m[e]

        # delete the directories first, in order of
        # increasing depth
        for currentDepth in xrange(0,maxDepth+1):
            for hashval, list in self.m.iteritems():
                example = list[0]
                if isinstance(example, DirObj):
                    winner, losers = resolve_candidates(list, currentDepth)
                    for loser in losers:
                        if not loser.deleted:
                            self.delete(loser)
                            print 'rm -rf "' + loser.pathname + '" # covered by ' + winner.pathname
                    self.prune()

        #print
        #print 'after dir purge'
        #self.display() 
        #print

        for hashval, list in self.m.iteritems():
            example = list[0]  
            if isinstance(example, FileObj):
                winner, losers = resolve_candidates(list)
                for loser in losers:
                    if not loser.deleted:
                        self.delete(loser)
                        print 'rm "' + loser.pathname + '" # covered by ' + winner.pathname
        #print
        #print 'after file purge'
        #self.display() 
        #print

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
                if not entry.deleted:
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
        return (self.files[fileName])

    def walk(self):
        for name, d in self.subdirs.iteritems():
            for dirEntry in d.walk():
                yield dirEntry
        yield self
        
    def delete(self):
        self.deleted=True
        for name, d in self.subdirs.iteritems():
            d.delete()
        for name, f in self.files.iteritems():
            f.delete()

    def prune_empty(self):
        changed=False

        for name, d in self.subdirs.iteritems():
            if not d.deleted:
                changed |= d.prune_empty()

        empty=True
        for name, d in self.subdirs.iteritems():
            if d.deleted == False:
                empty=False
        for name, f in self.files.iteritems():
            if f.deleted == False:
                empty=False
        if empty:
            self.delete()
            print 'rmdir "' + self.pathname + '"'
            changed=True

        return changed

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

    def count_deleted(self):
        if self.deleted:
            deleted=1
        else:
            deleted=0
        for name, d in self.subdirs.iteritems():
            deleted = deleted + d.count_deleted()
        for name, f in self.files.iteritems():
            if f.deleted:
                deleted = deleted + 1
        return deleted

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

    def delete(self):
        self.deleted=True

    def walk(self):             # cannot iterate over a file
        pass

    def prune_empty(self):
        return False            # can't prune a file

    def display(self, contents=False, recurse=False):
        print 'File\t\t' + str(self.deleted) + '\t' + str(self.depth) + '\t' + self.hexdigest + ' ' + self.pathname # + ' ' + str(os.stat(self.pathname))

    def count_deletedi(self):
        if self.deleted:
            return 1
        else:
            return 0

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
    elif issocket(entry):
        print 'Skipping a socket ' + entry
    elif os.path.isdir(entry):
        topDirEntry=DirObj(entry)
        topLevelList[entry]=topDirEntry
        for dirName, subdirList, fileList in os.walk(entry, topdown=False):
            dirEntry=topDirEntry.place_dir(dirName)
            for fname in fileList:
                if issocket(dirEntry.pathname + '/' + fname):
                    print 'Skipping a socket ' + dirEntry.pathname + '/' + fname
                else:
                    fileEntry=dirEntry.place_file(fname)
    else:
        print "I don't know what this is" + entry

deleted=1
while deleted > 0:
    h.purge()
    maxDepth=1      # i assume at least one file or dir here
    for name, e in topLevelList.iteritems():
        for dirEntry in e.walk():
            #print '\nadding dir ' + dirEntry.pathname
            if not dirEntry.deleted:
                for name, fileEntry in dirEntry.files.iteritems():
                    if not fileEntry.deleted:
                        h.addEntry(fileEntry)
                        #print 'added file ' + fileEntry.pathname
                    else:
                        #print 'skipping deleted file ' + fileEntry.pathname
                        pass
                dirEntry.close()
                h.addEntry(dirEntry)
                #print 'added dir ' + dirEntry.pathname
            else:
                #print 'skipping deleted dir ' + dirEntry.pathname
                pass
        td=e.max_depth()
        if maxDepth < td:
            maxDepth=td

    prevCount=0
    for name, e in topLevelList.iteritems():
        prevCount = prevCount + e.count_deleted()

    h.resolve(maxDepth)
    for name, e in topLevelList.iteritems():
        while e.prune_empty():
            pass

    afterCount=0
    for name, e in topLevelList.iteritems():
        afterCount = afterCount + e.count_deleted()

    deleted=afterCount - prevCount
    #print str(deleted) + ' entries deleted'

for name, e in topLevelList.iteritems():
    pass
    #e.display(True,True)

