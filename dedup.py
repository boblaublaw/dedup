#!/usr/bin/env python

import hashlib
import os
import sys
import stat
import time
import argparse
from operator import attrgetter
from itertools import ifilter

# what to export when other scripts import this module:
__all__ = ["FileObj", "DirObj", "EntryObj", "HashDbObj" ]

# TODO exclude and include filters

# CONSTANTS:

# This list represents files that may linger in directories preventing
# this algorithm from recognizing them as empty.  we mark them as
# deletable, even if we do NOT have other copies available:
DELETE_LIST =    [ "album.dat", "album.dat.lock", "photos.dat",
                "photos.dat.lock", "Thumbs.db", ".lrprev", "Icon\r",
                ".dropbox.cache", ".DS_Store", "desktop.ini",
                ".dropbox.attr" ]

# This list describes files and directories we do not want to risk
# messing with.  If we encounter these, never mark them as deletable.
# TODO - implement this
DO_NOT_DELETE_LIST = []

# size of hashing buffer:
BUF_SIZE = 65536

# default globals
reverseSort=False
deleteEmptyFiles = True    # TODO make this a CLI switch
deleteEmptyDirs = True      # TODO make this a CLI switch
verbosity = 0
db = None

def member_is_type(tuple, type):
    """for checking the type of a list member which is also packed in a 
    tuple. This function assumes all list members are the same type.
    """
    list=tuple[1]
    return isinstance(list[0], type)

def compute_hash(pathname):
    """reads a file and computes a SHA1 hash"""
    # open and read the file
    sha1 = hashlib.sha1()
    with open(pathname, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    digest = sha1.hexdigest()
    if verbosity > 0:
        print '# computed new hash ' + digest,
        print 'for ' + pathname
    return digest

def get_hash(f):
    """returns a hash for a filename"""
    global db
    if db is not None:
        return db.lookup_hash(f)
    return(compute_hash(f.abspathname))

def issocket(path):
    """For some reason python provides isfile and isdirectory but not
    issocket().
    """
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

def generate_delete(filename):
    """generates not-quite-safe rm commands.  TODO does not handle
    pathnames which contain both the ' and " characters.
    """
    # characters that we will wrap with double quotes:
    delimTestChars = set("'()")
    if any((c in delimTestChars) for c in filename):
        print 'rm -rf "' + filename + '"'
    else:
        print "rm -rf '" + filename + "'"

def check_int(s):
    """helper function that returns true if you pass in a string that
    represents an integer
    """
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

def check_level(pathname):
    """inspects a pathname for a weight prefix on the front.  This
    completely breaks files that actually start with "<int>:"
    """
    parts = pathname.split(':')
    if len(parts) > 1:
        firstPart = parts.pop(0)
        remainder = ':'.join(parts)
        if check_int(firstPart):
            return int(firstPart), remainder

    # if anything goes wrong just fail back to assuming the whole
    # thing is a path without a weight prefix.
    return 0, pathname

def generate_map_header(winnerMap, name):
    """Turns a report into a list of stats"""
    winnerList = winnerMap.keys()
    winCount = 0 
    loserCount = 0 
    loserBytes = 0
    for winner in winnerList:
        winCount = winCount + 1 
        losers = winnerMap[winner]
        for loser in losers:
            loserCount = loserCount + 1 
            loserBytes = loserBytes + loser.count_bytes(deleted=True)
    print "\n" + '#' * 72
    print '# ' + str(winCount), 
    if loserCount == 0:
        just_a_list = True
        print name
    else:
        just_a_list = False
        print 'winner and ' + str(loserCount) + ' loser ' + name,
        print str(loserBytes) + ' bytes redundant'
    return just_a_list

def generate_map_commands(winnerMap, name):
    winnerList = winnerMap.keys()
    if len(winnerList) == 0:
        return
    just_a_list = generate_map_header(winnerMap, name)

    winnerList.sort()
    if just_a_list:
        for winner in winnerList:
            generate_delete(winner)
    else:
        for winner in winnerList:
            losers = winnerMap[winner]
            print "#      '" + winner + "'" 
            for loser in losers:
                generate_delete(loser.abspathname)
            print


class EntryList:
    """A container for all source directories and files to examine"""
    def __init__(self, arguments, staggerPaths):
        self.contents = {}
        stagger = 0;

        # walk arguments adding files and directories
        for entry in arguments:
            # strip trailing slashes, they are not needed
            entry = entry.rstrip('/')

            # check if a weight has been provided for this argument
            weightAdjust, entry = check_level(entry)

            if os.path.isfile(entry):
                if staggerPaths:
                    weightAdjust = weightAdjust + stagger
                newFile = FileObj(entry, weightAdjust = weightAdjust)
                if staggerPaths:
                    stagger = stagger + newFile.depth
                self.contents[entry] = newFile
            elif issocket(entry):
                print '# Skipping a socket ' + entry
            elif os.path.isdir(entry):
                if staggerPaths:
                    weightAdjust = weightAdjust + stagger
                topDirEntry = DirObj(entry, weightAdjust)
                self.contents[entry] = topDirEntry
                for dirName, subdirList, fileList in os.walk(entry,
                                                        topdown = False):
                    dirEntry = topDirEntry.place_dir(dirName,
                                                        weightAdjust)
                    for fname in fileList:
                        if issocket(dirEntry.abspathname + '/' + fname):
                            print '# Skipping a socket',
                            print dirEntry.abspathname + '/' + fname
                        else:
                            newFile = FileObj(fname,
                                            parent = dirEntry,
                                            weightAdjust = weightAdjust)
                            dirEntry.files[fname]=newFile
                if staggerPaths:
                    stagger = topDirEntry.max_depth()
            else:
                print "I don't know what this is" + entry
                sys.exit()

    # EntryList.count_bytes
    def count_bytes(self, deleted=False):
        """Returns a btyecount of all the (deleted) objects within"""
        bytes = 0
        for name, e in self.contents.iteritems():
            bytes = bytes + e.count_bytes(deleted)
        return bytes

    # EntryList.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        count = 0
        for name, e in self.contents.iteritems():
            count = count + e.count_deleted()
        return count

    # EntryList.prune_empty
    def prune_empty(self):
        """Flags all the children of the deleted objects within to also
        be deleted.
        """
        prevCount = self.count_deleted()
        if deleteEmptyDirs:
            for name, e in allFiles.contents.iteritems():
                e.prune_empty()
        return allFiles.count_deleted() - prevCount

    # EntryList.walk
    def walk(self):
        for name, topLevelItem in allFiles.contents.iteritems():
            for item in topLevelItem.walk():
                yield item


class HashMap:
    """A wrapper to a python dict with some helper functions"""
    def __init__(self, allFiles):
        self.contentHash = {}
        self.minDepth = 1
        self.maxDepth = 0
        # we will use this later to count deletions:
        self.allFiles = allFiles

        for name, e in allFiles.contents.iteritems():
            if isinstance(e, FileObj):
                self.add_entry(e)
            else:
                for dirEntry in ifilter(
                        lambda x: x.deleted is False, 
                        e.dirwalk()):
                    for name, fileEntry in ifilter(
                            lambda x: x[1].deleted is False,  
                            dirEntry.files.iteritems()):
                        self.add_entry(fileEntry)
                    dirEntry.finalize()
                    self.add_entry(dirEntry)
            maxd = e.max_depth()
            if self.maxDepth < maxd:
                self.maxDepth = maxd

    # HashMap.add_entry
    def add_entry(self, entry):
        """Store a file or directory in the HashMap, indexed by it's
        hash, and then further appended to a list of other entries
        with the same hash.
        """
        if entry.hexdigest in self.contentHash:
            self.contentHash[entry.hexdigest].append(entry)
        else:
            self.contentHash[entry.hexdigest] = [ entry ]
        if entry.depth < self.minDepth:
            self.minDepth = entry.depth

    # HashMap.display
    def display(self):
        """Generate a human readable report."""
        for hashval, list in self.contentHash.iteritems():
            for entry in list:
                entry.display(False, False)

    # HashMap.prune
    def prune(self):
        """Removes deleted objects from the HashMap"""
        deleteList = []
        for hashval, list in self.contentHash.iteritems():
            trimmedList=[]
            for entry in list:
                if entry.deleted:
                    entry.delete()
                else:
                    trimmedList.append(entry)
            # store the trimmed list
            if len(trimmedList) > 0:
                self.contentHash[hashval]=trimmedList
            else:
                # if no more entries exist for this hashval,
                # remove the entry from the dict:
                deleteList.append(hashval)

        # remove deleted items from the hash lookup dict:
        for entry in deleteList:
            del self.contentHash[entry]

    # HashMap.resolve_candidates
    def resolve_candidates(self, candidates):
        """Helper function which examines a list of candidate objects with
        identical contents (as determined elsewhere) to determine which of
        the candidates is the "keeper" (or winner).  The other candidates
        are designated losers.  The winner is selected by comparing the
        depths of the candidates.  If reverseSort is true, the deepest
        candidate is chosen, else the shallowest is chosen.  In the case
        of a tie, the length of the full path is compared.
        """
        if len(candidates) == 0:
            return

        global reverseSort
        candidates.sort(
            key=attrgetter('depth','abspathnamelen','abspathname'), 
            reverse=reverseSort)
        winner = candidates.pop(0)

        if isinstance(winner, DirObj) and winner.is_empty():
            # we trim empty directories using DirObj.prune_empty()
            # because it produces less confusing output
            return

        if isinstance(winner, FileObj) and winner.bytes == 0:
            # we also trim empty files
            return

        losers = []
        # once we have a winner, mark all the other candidates as losers
        for candidate in candidates:
            if candidate != winner:
                losers.append(candidate)
                if not candidate.deleted:
                    candidate.delete()
                    if verbosity > 0:
                        if isinstance(candidate,DirObj):
                            print '# dir  "' + candidate.abspathname,
                        else:
                            print '# file "' + candidate.abspathname,
                        print '" covered by "' + winner.abspathname + '"'
                    candidate.winner = winner

        winner.losers = losers

    # HashMap.resolve
    def resolve(self):
        """Compares all entries and where hash collisions exists, pick a
        keeper.
        """
        global verbosity
        prevCount = self.allFiles.count_deleted()

        # no need to resolve uniques, so remove them from the HashMap
        uniques=[]
        # you cannot modify a collection while iterating over it...
        for hashval, list in self.contentHash.iteritems():
            if len(list) == 1:
                uniques.append(hashval)
        # ... so delete entries in a second pass.
        for entry in uniques:
            del self.contentHash[entry]

        # delete the directories first, in order of (de/in)creasing depth,
        # depending on the reverseSort setting.
        #
        # This approach isn't strictly required but it results in fewer
        # calls to this function if we delete leaf nodes first, as it will
        # allow non-leaf directories to match on subsequent calls to 
        # resolve().

        depths=range(self.minDepth-1,self.maxDepth+1)
        global reverseSort
        if reverseSort:
            depths.reverse()
        if verbosity > 0:
            print '# checking candidates in dir depth order:',
            print str(depths)

        for depthFilter in depths:
            #print '# checking depth ' + str(depthFilter)
            for hashval, candidates in ifilter(lambda x: 
                    member_is_type(x,DirObj),self.contentHash.iteritems()):
                if reverseSort:
                    maybes = [x for x in candidates if x.depth < depthFilter ]
                else:
                    maybes = [x for x in candidates if x.depth > depthFilter ]
                if len(maybes) > 0:
                    self.resolve_candidates(maybes)
            self.prune()

        for hashval, candidates in ifilter(lambda x: member_is_type(x,FileObj),self.contentHash.iteritems()):
            self.resolve_candidates(candidates)
        self.prune()

        return self.allFiles.count_deleted() - prevCount


class DirObj():
    """A directory object which can hold metadata and references to
    files and subdirectories.
    """
    def __init__(self, name, weightAdjust=0, parent=None):
        self.name = name
        self.files = {}
        self.deleted = False
        self.winner = None
        self.subdirs = {}
        self.weightAdjust = weightAdjust
        self.parent = parent
        ancestry = self.get_lineage()
        self.pathname = '/'.join(ancestry)
        self.abspathname = os.path.abspath(self.pathname)
        self.abspathnamelen = len(self.abspathname)
        self.depth = len(ancestry) + self.weightAdjust
        self.ignore = self.name in DELETE_LIST

    # DirObj.get_lineage
    def get_lineage(self):
        """Crawls back up the directory tree and returns a list of
        parents.
        """
        if self.parent is None:
            return self.name.split('/')
        ancestry = self.parent.get_lineage()
        ancestry.append(self.name)
        return ancestry

    # DirObj.max_depth
    def max_depth(self):
        """Determine the deepest point from this directory"""
        md = self.depth
        if len(self.subdirs.keys()):
            for name, entry in self.subdirs.iteritems():
                if not entry.deleted:
                    td = entry.max_depth()
                    if td > md:
                        md = td
            return md
        elif len(self.files.keys()):
            return md + 1
        else:
            return md

    # DirObj.display
    def display(self, contents=False, recurse=False):
        """Generate a human readable report.
                'contents' controls if files are displayed
                'recurse' controls if subdirs are displayed
        """
        if recurse:
            for name, entry in self.subdirs.iteritems():
                entry.display(contents, recurse)
        if contents:
            for name, entry in self.files.iteritems():
                entry.display(contents, recurse);
        print '# Directory\t' + str(self.deleted) + '\t',
        print str(self.ignore) + '\t' + str(self.depth) + '\t',
        print self.hexdigest + ' ' + self.abspathname

    # DirObj.place_dir
    def place_dir(self, inputDirName, weightAdjust):
        """Matches a pathname to a directory structure and returns a
        DirObj object.
        """
        inputDirList = inputDirName.split('/')
        nameList = self.name.split('/')

        while (len(inputDirList) and len(nameList)):
            x = inputDirList.pop(0)
            y = nameList.pop(0)
            if x != y:
                print x + ' and ' + y + ' do not match'
                raise LookupError

        if len(inputDirList) == 0:
            return self

        nextDirName = inputDirList[0]
        if nextDirName in self.subdirs:
            tmpName='/'.join(inputDirList)
            tmpSub = self.subdirs[nextDirName]
            return tmpSub.place_dir(tmpName, weightAdjust)

        #print "did not find " + nextDirName + " in " + self.name
        nextDir = DirObj(nextDirName, weightAdjust, self)
        self.subdirs[nextDirName]=nextDir
        return nextDir.place_dir('/'.join(inputDirList), weightAdjust)

    # DirObj.dirwalk
    def dirwalk(self, topdown=False):
        """A generator which traverses just subdirectories"""
        if topdown:
            yield self
        for name, d in self.subdirs.iteritems():
            for dirEntry in d.dirwalk():
                yield dirEntry
        if not topdown:
            yield self

    # DirObj.walk
    def walk(self):
        """A generator which traverses files and subdirs"""
        for name, subdir in self.subdirs.iteritems():
            for e in subdir.walk():
                yield e
        for name, fileEntry in self.files.iteritems():
            yield fileEntry
        yield self

    # DirObj.delete
    def delete(self):
        """Mark this directory and all children as deleted"""
        self.deleted = True
        for name, d in self.subdirs.iteritems():
            d.delete()
        for name, f in self.files.iteritems():
            f.delete()

    # DirObj.generate_reports
    def generate_reports(self, reports):
        """Populates several "reports" that describe duplicated
        directories, files, as well as empty directories and files
        """
        dirReport = reports['dirs']
        emptyReport = reports['dirs that are empty after reduction']
        startedEmptyReport = reports['dirs that started empty']

        if self.deleted:
            if self.winner is not None:
                if self.winner.abspathname in dirReport:
                    # use existing loser list:
                    loserList = dirReport[self.winner.abspathname]
                    loserList.append(self)
                else:
                    # start a new loser list:
                    dirReport[self.winner.abspathname] = [ self ]
            else:
                # this is a cheat wherein I use the emptyReport as a list of keys
                # and I disregard the values
                if self.started_empty():
                    startedEmptyReport[self.abspathname]=[]
                else:
                    emptyReport[self.abspathname]=[]
        else:
            for fileName, fileEntry in self.files.iteritems():
                fileEntry.generate_reports(reports)
            for dirName, subdir in self.subdirs.iteritems():
                subdir.generate_reports(reports)

    # DirObj.started_empty
    def started_empty(self):
        """Checks if the dir was truly empty when the program was
        invoked.
        """
        return (len(self.files) + len(self.subdirs)) == 0
            
        for fileName, fileEntry in self.files.iteritems():
            if not fileEntry.deleted and not fileEntry.ignore:
                return False

        for dirName, subdir in self.subdirs.iteritems():
            if (not subdir.deleted
                    and not subdir.is_empty()
                    and not subdir.ignore):
                return False

        return True

    # DirObj.is_empty
    def is_empty(self):
        """Checks if the dir is empty, ignoring items marked as deleted
        or ignored.  (In other words, ignored items won't protect a 
        directory from being marked for deletion.)
        """
        for fileName, fileEntry in self.files.iteritems():
            if not fileEntry.deleted and not fileEntry.ignore:
                return False

        for dirName, subdir in self.subdirs.iteritems():
            if (not subdir.deleted
                    and not subdir.is_empty()
                    and not subdir.ignore):
                return False

        return True

    # DirObj.prune_empty
    def prune_empty(self):
        """Crawls through all directories and marks the shallowest
        empty entiries for deletion.
        """
        if (self.is_empty()
                and not self.deleted
                and self.parent is None):
            self.delete()
        elif (self.is_empty()
                and not self.deleted
                and self.parent is not None
                and not self.parent.is_empty()):
            self.delete()
        else:
            for dirname, dirEntry in self.subdirs.iteritems():
                dirEntry.prune_empty()

    # DirObj.finalize
    def finalize(self):
        """Once no more files or directories are to be added, we can
        create a meta-hash of all the hashes therein.  This allows us to
        test for directories which have the same contents.
        """
        digests = []
        for filename, fileEntry in self.files.iteritems():
            digests.append(fileEntry.hexdigest)
        for dirname, dirEntry in self.subdirs.iteritems():
            digests.append(dirEntry.hexdigest)
        digests.sort()
        sha1 = hashlib.sha1()
        for d in digests:
            sha1.update(d)
        self.hexdigest = sha1.hexdigest()
        global deleteEmptyDirs
        if (len(self.files) + len(self.subdirs)) == 0:
            self.deleted = deleteEmptyDirs
        

    # DirObj.count_bytes
    def count_bytes(self, deleted=False):
        """returns a count of all the sizes of the deleted objects
        within.
        """
        bytes = 0
        for name, d in self.subdirs.iteritems():
            bytes = bytes + d.count_bytes(deleted)
        for name, f in self.files.iteritems():
            if f.deleted and deleted:
                bytes = bytes + f.count_bytes(deleted)
            elif not f.deleted and not deleted:
                bytes = bytes + f.count_bytes(deleted)
        return bytes

    # DirObj.count_deleted
    def count_deleted(self):
        """returns a count of all the deleted objects within"""
        if self.deleted:
            deleted = 1
        else:
            deleted = 0
        for name, d in self.subdirs.iteritems():
            deleted = deleted + d.count_deleted()
        for name, f in self.files.iteritems():
            if f.deleted:
                deleted = deleted + 1
        return deleted


class FileObj():
    """A file object which stores some metadata"""
    def __init__(self, name, parent=None, weightAdjust = 0):
        self.name = name;
        self.winner = None
        self.parent = parent
        self.weightAdjust = weightAdjust
        self.ignore = self.name in DELETE_LIST

        if self.parent is not None:
            ancestry = self.parent.get_lineage()
            self.pathname = '/'.join(ancestry) + '/' + self.name
            self.depth = len(ancestry) + self.weightAdjust
        else:
            self.pathname = self.name
            self.depth = self.weightAdjust

        self.abspathname = os.path.abspath(self.pathname);
        self.abspathnamelen = len(self.abspathname)

        statResult = os.stat(self.abspathname)
        self.modTime = statResult.st_mtime
        self.createTime = statResult.st_ctime
        self.bytes = statResult.st_size
        self.hexdigest = get_hash(self)
        global deleteEmptyFiles
        if self.bytes == 0:
            self.deleted = deleteEmptyFiles or self.ignore
        else:
            self.deleted = self.ignore

    # FileObj.max_depth
    def max_depth(self):
        return self.depth

    # FileObj.walk
    def walk(self):
        """Used to fit into other generators"""
        yield self

    # FileObj.delete
    def delete(self):
        """Mark for deletion"""
        self.deleted = True

    # FileObj.generate_reports
    def generate_reports(self, reports):
        fileReport = reports['files']
        emptyReport = reports['empty files']
        """Generates delete commands to dedup all contents"""
        if self.deleted and not self.ignore:
            if self.winner is not None:
                # just a trivial check to confirm hash matches:
                if self.bytes != self.winner.bytes:
                    print '# BIRTHDAY LOTTERY CRISIS!'
                    print '# matched hashes and mismatched sizes!'
                    sys.exit(-1)
                if self.winner.abspathname in fileReport:
                    # use existing loserList
                    loserList = fileReport[self.winner.abspathname]
                    loserList.append(self)
                else:
                    # create a new loserList
                    fileReport[self.winner.abspathname] = [ self ]
            else:
                # this is a cheat wherein I use the emptyReport as a list of keys
                # and I disregard the values
                emptyReport[self.abspathname] = [ ]

    # FileObj.prune_empty
    def prune_empty(self):
        """Crawls through all directories and deletes the children of
        the deleted
        """
        return False            # can't prune a file

    # FileObj.display
    def display(self, contents=False, recurse=False):
        """Generate a human readable report."""
        print '# File\t\t' + str(self.deleted) + '\t',
        print str(self.ignore) + '\t' + str(self.depth) + '\t',
        print self.hexdigest + ' ' + self.pathname

    # FileObj.count_bytes
    def count_bytes(self, deleted=False):
        """Returns a count of all the sizes of the deleted objects
        within
        """
        if self.deleted and deleted:
             return self.bytes
        elif not self.deleted and not deleted:
            return self.bytes
        return 0 

    # FileObj.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        if self.deleted:
             return 1
        else:
            return 0


class HashDbObj():
    def __init__(self, pathname):
        self.pathname=pathname
        try:
            self.modTime = os.stat(self.pathname).st_mtime
        except OSError:
            print "# db " + self.pathname + " doesn't exist yet"
            self.modTime = time.time()
        print '# db last modification time is',
        print str(time.time() - self.modTime) + ' seconds ago'

        try:
            import gdbm
            self.dbType = 'gdbm'
        except ImportError:
            self.dbType='anydbm'
            print '# no gdbm implementation found, trying anydbm'
            try:
                import anydbm
            except ImportError:
                print '# no dbm implementation found!'
                sys.exit(-1)
        print '# set to use database ' + self.pathname,
        print 'of type: ' + self.dbType

        print '# loading database ' + self.pathname
        try:
            if self.dbType == 'gdbm':
                self.db = gdbm.open(self.pathname, 'c')
            elif self.dbType == 'anydbm':
                self.db = anydbm.open(self.pathname, 'c')
        except: # TODO name the exception here
            print "# " + self.pathname + " could not be loaded"
            sys.exit(-1)

    def lookup_hash(self, f):
        """look up this path to see if it has already been computed"""
        global verbosity
        if f.abspathname in self.db:
            # we've a cached hash value for this abspathname
            if f.modTime > self.modTime:
                # file is newer than db
                pass
            else:
                # db is newer than file
                digest = self.db[f.abspathname]
                if verbosity > 0:
                    print '# hash ' + digest + ' for ' + f.abspathname + ' already in db.'
                return digest
        digest=compute_hash(f.abspathname)
        # add/update the cached hash value for this entry:
        self.db[f.abspathname]=digest
        return digest

    def clean(self):
        """function to remove dead nodes from the hash db"""
        global verbosity
        if self.dbType != 'gdbm':
            print '# non-gdbm databases (' + self.dbType + ') dont support the',
            print 'reorganize method!'
            sys.exit(-1)

        startTime = time.time()
        print '# Starting database clean...'
        # even though gdbm supports memory efficient iteration over
        # all keys, I want to order my traversal across similar
        # paths to leverage caching of directory files:
        allKeys = self.db.keys()
        print '# finished loaded keys from ' + self.pathname
        allKeys.sort()
        print '# finished sorting keys from ' + self.pathname
        print '# deleting dead nodes'
        misscount = 0
        hitcount = 0
        for currKey in allKeys:
            try:
                os.stat(currKey)
            except OSError:
                del self.db[currKey]
                if verbosity > 0:
                    sys.stdout.write('*')
                    sys.stdout.flush()
                misscount = misscount+1
            else:
                hitcount = hitcount + 1
                if verbosity > 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
        print "\n# reorganizing " + self.pathname
        self.db.reorganize()
        self.db.sync()
        print '# done cleaning ' + self.pathname + ', removed',
        print str(misscount) + ' dead nodes and kept ' + str(hitcount),
        print 'nodes!'
        endTime = time.time()
        print '# Database clean complete after ' + str(endTime - startTime),
        print 'seconds.'

if __name__ == '__main__':
    startTime = time.time()
    desc="generate commands to eliminate redundant files and directories"
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                    help="increase output verbosity")
    parser.add_argument("-d", "--database", 
                    help="name of DBM file to use for hash cache")
    parser.add_argument("-c", "--clean-database", action="store_true",
                    help="clean hash cache instead of normal operation")
    parser.add_argument("-s", "--stagger-paths", action="store_true",
                    help="always prefer files in argument order")
    parser.add_argument("-r", "--reverse-sort", action="store_true",
                    help="reverse the dir/file selection choices")
    args, paths = parser.parse_known_args()

    verbosity = args.verbosity
    reverseSort = args.reverse_sort

    if args.database is not None:
        db=HashDbObj(args.database)

    if args.clean_database and db is None:
        print '# database file must be specified for --clean-database',
        print 'command (use -d)'
        sys.exit(-1)

    if len(paths) == 0 and args.stagger_paths:
            print '# -s/--stagger-paths specified, but no paths provided!'
            sys.exit(-1)

    if args.clean_database:
        db.clean()

    if len(paths) > 0:
        allFiles = EntryList(paths, args.stagger_paths)
        passCount = 0
        # fake value to get the loop started:
        deleted = 1
        # while things are still being removed, keep working:
        while deleted > 0:
            sys.stdout.flush()
            h = HashMap(allFiles)
            deletedDirectories = allFiles.prune_empty()

            h = HashMap(allFiles)
            deletedHashMatches = h.resolve()

            deleted = deletedDirectories + deletedHashMatches
            passCount = passCount + 1
            if deleted > 0:
                print '# ' + str(deleted) + ' entries deleted on pass',
                print str(passCount)

        reports = { 'dirs': {},
                    'files': {},
                    'dirs that are empty after reduction': {},
                    'dirs that started empty': {},
                    'empty files': {},
                    }

        for name, e in allFiles.contents.iteritems():
            e.generate_reports(reports)

        for reportName, report in reports.iteritems():
            generate_map_commands(report, reportName)

        #for e in allFiles.walk():
        #    e.display(False,False)
        endTime = time.time()
        print '# total bytes marked for deletion (not including',
        print 'directory files): ' + str(allFiles.count_bytes(deleted=True))
        print '# total dedup running time: ' + str(endTime - startTime),
        print 'seconds.'

# vim: set expandtab sw=4 ts=4:
