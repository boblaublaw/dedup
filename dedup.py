#!/usr/bin/env python

import hashlib, os, sys, stat, anydbm, time

# TODO need ignore lists for files and dirs to disregard
ignoreList = [ "Icon\r", '.git', '.dropbox.cache', '.DS_Store' ]

# for some reason python provides isfile and isdirectory but not issocket
def issocket(path):
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

# a helper function that determines which file/dir to keep and which to remove
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
            if len(incumbent.pathname) > len(candidate.pathname):
                depthMap[candidate.depth] = candidate
            
    k=depthMap.keys()
    if len(k) == 0:
        # nothing to resolve at this depth
        return None, losers

    k.sort()
    md=k.pop(0)
    # we choose the candidate closest to the root 
    # deeper candidates are the losers
    # TODO other criteria?
    winner=depthMap[md]

    if isinstance(winner, DirObj) and winner.is_empty():
        return None, None

    for candidate in candidates:
        if candidate != winner:
            losers.append(candidate)
    return winner, losers
        
class EntryList:
    """a container for all source directories and files to examine"""
    def __init__(self, argv, databasePathname):
        self.contents = {}
        self.modTime = None
        self.db = None

        try:
            self.modTime = os.stat(databasePathname + '.db').st_mtime
        except OSError:
            print "# db " + databasePathname + ".db doesn't exist yet"
            self.modTime = None

        if databasePathname != None:
            self.db = anydbm.open(databasePathname, 'c')
            if self.modTime == None:
                self.modTime = time.time()

        print '# db modTime is ' + str(time.time() - self.modTime) + ' seconds ago'
        # walk argv adding files and directories
        for entry in argv:
            # TODO strip trailing slashes
            if os.path.isfile(entry):
                self.contents[entry]=FileObj(entry, dbTime=self.modTime, db=self.db)
            elif issocket(entry):
                print '# Skipping a socket ' + entry
            elif os.path.isdir(entry):
                topDirEntry=DirObj(entry)
                self.contents[entry]=topDirEntry
                for dirName, subdirList, fileList in os.walk(entry, topdown=False):
                    dirEntry=topDirEntry.place_dir(dirName)
                    for fname in fileList:
                        if issocket(dirEntry.pathname + '/' + fname):
                            print '# Skipping a socket ' + dirEntry.pathname + '/' + fname
                        else:
                            dirEntry.files[fname]=FileObj(fname, parent=dirEntry, dbTime=self.modTime, db=self.db)
            else:
                print "I don't know what this is" + entry
                sys.exit()
        if self.db != None:
            self.db.close()

    def count_deleted(self):
        count=0
        for name, e in self.contents.iteritems():
            count = count + e.count_deleted()
        return count

    def prune_empty(self):
        prevCount = self.count_deleted()
        for name, e in allFiles.contents.iteritems():
            e.prune_empty()
        return allFiles.count_deleted() - prevCount

    def generate_commands(self):
        for name, e in allFiles.contents.iteritems():
            e.generate_commands()

class HashMap:
    """A wrapper to a python dict with some helper functions"""
    def __init__(self,allFiles):
        self.contentHash = {}
        self.maxDepth = 1 # we assume at least one file or dir
        self.allFiles=allFiles # we will use this later to count deletions

        for name, e in allFiles.contents.iteritems():
            if isinstance(e, FileObj):
                self.add_entry(e)
                continue
            for dirEntry in e.walk():
                #print '\n# adding dir ' + dirEntry.pathname
                if not dirEntry.deleted:
                    for name, fileEntry in dirEntry.files.iteritems():
                        if not fileEntry.deleted:
                            self.add_entry(fileEntry)
                            #print '# added file ' + fileEntry.pathname
                        else:
                            #print '# skipping deleted file ' + fileEntry.pathname
                            pass
                    dirEntry.close()
                    self.add_entry(dirEntry)
                    #print '# added dir ' + dirEntry.pathname
                else:
                    #print '# skipping deleted dir ' + dirEntry.pathname
                    pass
            td=e.max_depth()
            if self.maxDepth < td:
                self.maxDepth=td

    def add_entry(self, entry):
        # hash digest value
        hv=entry.hexdigest
        
        if hv in self.contentHash:
            self.contentHash[hv].append(entry)
        else:
            self.contentHash[hv] = [ entry ]

    def display(self):
        for hashval, list in self.contentHash.iteritems():
            for entry in list:
                entry.display(False, False)

    def delete(self, entry):
        # mark this entry (and any children) as deleted
        entry.delete()

        # remove the entry from the hashmap
        list=self.contentHash[entry.hexdigest]
        newlist = []
        for e in list:
            if e != entry:
                newlist.append(e)

        # if there are no more entries for this hashval, remove
        # it from the dictionary m
        if len(newlist):
            self.contentHash[entry.hexdigest] = newlist
        else:
            del self.contentHash[entry.hashval]

        # also remove all the deleted children from the hashmap
        self.prune()

    def prune(self):
        # removes deleted objects from the hashMap
        for hashval, list in self.contentHash.iteritems():
            newlist=[]
            for entry in list:
                if not entry.deleted:
                    newlist.append(entry)
            self.contentHash[hashval]=newlist

    def resolve(self):
        prevCount = self.allFiles.count_deleted()

        # no need to resolve uniques, so remove them from the dict 
        deleteList=[]
        for hashval, list in self.contentHash.iteritems():
            if len(list) == 1:
                deleteList.append(hashval)
        for e in deleteList:
            del self.contentHash[e]

        # delete the directories first, in order of
        # increasing depth
        for currentDepth in xrange(0,self.maxDepth+1):
            for hashval, list in self.contentHash.iteritems():
                example = list[0]
                if isinstance(example, DirObj):
                    winner, losers = resolve_candidates(list, currentDepth)
                    if losers != None:
                        for loser in losers:
                            if not loser.deleted:
                                self.delete(loser)
                                #print 'rm -rf "' + loser.pathname + '" # covered by ' + winner.pathname
                                loser.reason = '"' + winner.pathname + '" makes dir redundant:'
                        self.prune()

        for hashval, list in self.contentHash.iteritems():
            example = list[0]  
            if isinstance(example, FileObj):
                winner, losers = resolve_candidates(list)
                for loser in losers:
                    if not loser.deleted:
                        self.delete(loser)
                        #print 'rm "' + loser.pathname + '" # covered by ' + winner.pathname
                        loser.reason = '"' + winner.pathname + '" makes file redundant:'

        return self.allFiles.count_deleted() - prevCount

class DirObj():
    """A directory object which can hold metadata and references to files and subdirectories"""
    def __init__(self, name, parent=None):
        self.name=name
        self.files={}
        self.deleted=False
        self.reason=""
        self.subdirs={}
        self.parent=parent
        ancestry=self.get_lineage()
        self.pathname='/'.join(ancestry) 
        self.depth=len(ancestry)
        self.ignore=self.name in ignoreList

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
        print '# Directory\t' + str(self.deleted) + '\t' + str(self.ignore) + '\t' + str(self.depth) + '\t' + self.hexdigest + ' ' + self.pathname + ' ' + self.reason

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

    def walk(self, topdown=False):
        if topdown:
            yield self
        for name, d in self.subdirs.iteritems():
            for dirEntry in d.walk():
                yield dirEntry
        if not topdown:
            yield self
        
    def delete(self):
        self.deleted=True
        for name, d in self.subdirs.iteritems():
            d.delete()
        for name, f in self.files.iteritems():
            f.delete()

    def generate_commands(self):
        if self.deleted and not self.ignore:
            print '#  ' + self.reason
            print 'rm -rf "' + self.pathname + '"'
        else:
            for fileName, fileEntry in self.files.iteritems():
                fileEntry.generate_commands()
            for dirName, subdir in self.subdirs.iteritems():
                subdir.generate_commands()

    def is_empty(self):
        # TODO what to do with ignored files/dirs?
        for fileName, fileEntry in self.files.iteritems():
            if not fileEntry.deleted:
                return False

        for dirName, subdir in self.subdirs.iteritems():
            if not subdir.deleted and not subdir.is_empty():
                return False
        return True

    def prune_empty(self):
        # find the highest empty nodes in the tree
        #print '# checking ' + self.pathname + ' for empties'
        if self.is_empty() and not self.deleted and self.parent != None and not self.parent.is_empty():
            #print 'rm -rf "' + self.pathname + '" # top of empty directory tree'
            self.delete()
            self.reason = "non-unique or empty directory:"
        else:
            #print '# ' + self.pathname + ' is not empty' + str(self.is_empty())
            for dirname, dirEntry in self.subdirs.iteritems():
                dirEntry.prune_empty()

    def close(self):
        digests=[]
        for filename, fileEntry in self.files.iteritems():
            digests.append(fileEntry.hexdigest)
        for dirname, dirEntry in self.subdirs.iteritems():
            digests.append(dirEntry.hexdigest)
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
    """A file object which stores some metadata"""
    def __init__(self, name, parent=None, dbTime=None, db=None):
        self.name=name;
        self.reason=""
        self.parent = parent
        self.deleted=False
        self.ignore=self.name in ignoreList

        if self.parent != None:
            ancestry=self.parent.get_lineage()
            self.pathname='/'.join(ancestry) + '/' + self.name
            self.depth=len(ancestry) + 1
        else:
            self.pathname=self.name
            self.depth=0

        self.modTime = os.stat(self.pathname).st_mtime

        #print '# ' + self.pathname + ' is ' + str(dbTime - self.modTime) + ' seconds older than the db'
        if db != None and self.pathname in db:
            # we've a cached hash value for this pathname
            if self.modTime > dbTime:
                # file is newer than db
                #print '# ' + self.pathname + ' is newer than the db'
                pass
            else:
                # db is newer than file
                #print '# ' + self.pathname + ' already in db'
                self.hexdigest=db[self.pathname]
                return
        elif db != None:
            #print '# ' + self.pathname + ' not in db'
            pass

        # open and read the file
        sha1 = hashlib.sha1()
        with open(self.pathname, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
        self.hexdigest=sha1.hexdigest()

        #print '# computed new hash for ' + self.pathname

        if db != None:
            # add/update the cached hash value for this entry
            #if self.pathname in db:
            #    print '# updating db entry for ' + self.pathname
            #else:
            #    print '# inserting db entry for ' + self.pathname
            db[self.pathname]=self.hexdigest

    def delete(self):
        self.deleted=True

    def generate_commands(self):
        if self.deleted and not self.ignore:
            print '#  ' + self.reason
            print 'rm "' + self.pathname + '"'

    def walk(self, topdown=False):             # cannot iterate over a file
        pass

    def prune_empty(self):
        return False            # can't prune a file

    def display(self, contents=False, recurse=False):
        print '# File\t\t' + str(self.deleted) + '\t' + str(self.ignore) + '\t' + str(self.depth) + '\t' + self.hexdigest + ' ' + self.pathname + ' ' + self.reason

    def count_deleted(self):
        if self.deleted:
            return 1
        else:
            return 0

BUF_SIZE = 65536  
sys.argv.pop(0)             # do away with the command itself
# defaults
pruneDirectories=True
databasePathname=None
again=True
while again:
    nextArg=sys.argv[0]     # peek ahead
    again=False
    if nextArg == '-np' or nextArg == '--no-prune-empty-directories':
        pruneDirectories=False
        sys.argv.pop(0)
        again=True
    elif nextArg == '-db' or nextArg == '--database':
        sys.argv.pop(0)
        databasePathname=sys.argv.pop(0)
        again=True

if databasePathname != None:
    print '# set to load hashes from ' + databasePathname

allFiles = EntryList(sys.argv, databasePathname)

passCount=0
deleted=1                   # fake value to get the loop started
while deleted > 0:          # while things are still being removed, keep working

    if pruneDirectories:
        h = HashMap(allFiles)
        deletedDirectories = allFiles.prune_empty()
    else:
        deletedDirectories=0

    h = HashMap(allFiles)
    deletedHashMatches = h.resolve()

    deleted = deletedDirectories + deletedHashMatches
    passCount = passCount + 1
    if deleted > 0:
        print '# ' + str(deleted) + ' entries deleted on pass ' + str(passCount)

allFiles.generate_commands()

#for name, e in allFiles.contents.iteritems():
#    pass
#    e.display(True,True)
