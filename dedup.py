#!/usr/bin/env python

import hashlib
import os
import sys
import stat
import time
import argparse

# what to export when other scripts import this module:
__all__ = ["FileObj", "DirObj", "EntryObj", "clean_database" ]

# TODO exclude and include filters

# CONSTANTS:

# This list represents files that may linger in directories preventing
# this algorithm from recognizing them as empty.  we mark them as
# deletable, even if we do NOT have other copies available:
DELETE_LIST =    [ "album.dat", "album.dat.lock", "photos.dat",
               "photos.dat.lock", "Thumbs.db", ".lrprev", "Icon\r",
                '.dropbox.cache', '.DS_Store' ]

# This list describes files and directories we do not want to risk
# messing with.  If we encounter these, never mark them as deletable.
# TODO - implement this
DO_NOT_DELETE_LIST = []

# size of hashing buffer:
BUF_SIZE = 65536

# defaults
verbosity = 0
databasePathname = None
cleanDatabase = False
staggerPaths = False
dbm = None

def resolve_candidates(candidates, currentDepth=None):
    """Helper function which examines a list of candidate objects with
    identical contents (as determined elsewhere) to determine which of
    the candidates is the "keeper" (or winner).  The other candidates
    are designated losers.  The winner is selected by incrementally
    increasing the directory depth (from 0) until one of the
    candidates is encountered.
    """
    depthMap = {}
    losers = []

    for candidate in candidates:
        if currentDepth is None and candidate.depth > currentDepth:
            # this candidate is too deep
            continue
        if candidate.depth not in depthMap:
            # encountered a new candidate, lets store it
            depthMap[candidate.depth] = candidate
        else:
            # found another candidate at the same depth
            incumbent = depthMap[candidate.depth]
            # use pathname length as a tie-breaker
            if len(incumbent.pathname) > len(candidate.pathname):
                depthMap[candidate.depth] = candidate

    k = depthMap.keys()
    if len(k) == 0:
        # nothing to resolve at this depth
        return None, None

    k.sort()
    md = k.pop(0)
    # we choose the candidate closest to the root
    # deeper candidates are the losers
    winner = depthMap[md]

    if isinstance(winner, DirObj) and winner.is_empty():
        # we trim empty directories using DirObj.prune_empty()
        # because it produces less confusing output
        return None, None

    # once we have a winner, mark all the other candidates as losers
    for candidate in candidates:
        if candidate != winner:
            losers.append(candidate)

    return winner, losers

def issocket(path):
    """For some reason python provides isfile and isdirectory but not
    issocket().
    """
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

def generate_delete(filename):
    # characters that we will wrap with double quotes:
    delimTestChars = set("'()")
    if any((c in delimTestChars) for c in filename):
        print 'rm -rf "' + filename + '"'
    else:
        print "rm -rf '" + filename + "'"

def check_int(s):
    if s[0] in ('-', '+'):
        return s[1:].isdigit()
    return s.isdigit()

def check_level(pathname):
    parts = pathname.split(':')
    if len(parts) > 1:
        firstPart = parts.pop(0)
        remainder = ':'.join(parts)
        if check_int(firstPart):
            return int(firstPart), remainder

    # if anything goes wrong just fail back to assuming the whole
    # thing is a path without a weight prefix.
    return 0, pathname


class EntryList:
    """A container for all source directories and files to examine"""
    def __init__(self, arguments, databasePathname, staggerPaths):
        self.contents = {}
        self.modTime = None
        self.db = None
        stagger = 0;

        if databasePathname is not None:
            try:
                import gdbm
                dbm = 'gdbm'
            except ImportError:
                dbm = 'anydbm'
                print '# no gdbm implementation found, trying anydbm'
                try:
                    import anydbm
                except ImportError:
                    print '# no dbm implementation found!'
                    sys.exit(-1)
            try:
                self.modTime = os.stat(databasePathname).st_mtime
            except OSError:
                print "# db " + databasePathname + " doesn't exist yet"
                self.modTime = None

            if dbm == 'gdbm':
                self.db = gdbm.open(databasePathname, 'c')
            elif dbm == 'anydbm':
                self.db = anydbm.open(databasePathname, 'c')

            if self.modTime is None:
                self.modTime = time.time()

            print '# db last modification time is',
            print str(time.time() - self.modTime) + ' seconds ago'

        # walk arguments adding files and directories
        for entry in arguments:
            # strip trailing slashes, they are not needed
            entry = entry.rstrip('/')

            # check if a weight has been provided for this argument
            weightAdjust, entry = check_level(entry)

            if os.path.isfile(entry):
                if staggerPaths:
                    weightAdjust = weightAdjust + stagger
                newFile = FileObj(entry,
                            dbTime = self.modTime,
                            db = self.db,
                            weightAdjust = weightAdjust)
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
                        if issocket(dirEntry.pathname + '/' + fname):
                            print '# Skipping a socket',
                            print dirEntry.pathname + '/' + fname
                        else:
                            newFile = FileObj(fname,
                                            parent = dirEntry,
                                            dbTime = self.modTime,
                                            db = self.db,
                                            weightAdjust = weightAdjust)
                            dirEntry.files[fname]=newFile
                if staggerPaths:
                    stagger = topDirEntry.max_depth()
            else:
                print "I don't know what this is" + entry
                sys.exit()
        if self.db is not None:
            self.db.close()

    # EntryList.count_deleted_bytes
    def count_deleted_bytes(self):
        """Returns a btyecount of all the deleted objects within"""
        bytes = 0
        for name, e in self.contents.iteritems():
            bytes = bytes + e.count_deleted_bytes()
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
        for name, e in allFiles.contents.iteritems():
            e.prune_empty()
        return allFiles.count_deleted() - prevCount

    # EntryList.walk
    def walk(self):
        for name, topLevelItem in allFiles.contents.iteritems():
            for item in topLevelItem.walk():
                yield item

    # EntryList.generate_commands
    def generate_commands(self):
        """Generates delete commands to dedup all contents"""

        selectDirMap={}
        selectFileMap={}
        emptyMap={}

        for name, e in self.contents.iteritems():
            e.generate_commands(selectDirMap, selectFileMap, emptyMap)

        winnerList = selectDirMap.keys()
        if len(winnerList):
            print '#' * 72
            print '# redundant directories:'
            winnerList.sort()
            for winner in winnerList:
                losers = selectDirMap[winner]
                print "#      '" + winner + "'"
                for loser in losers:
                    generate_delete(loser)
                print

        winnerList = selectFileMap.keys()
        if len(winnerList):
            print '#' * 72
            print '# redundant files:'
            winnerList.sort()
            for winner in winnerList:
                losers = selectFileMap[winner]
                print "#      '" + winner + "'"
                for loser in losers:
                    generate_delete(loser)
                print

        emptyDirs = emptyMap.keys()
        if len(emptyDirs):
            print '#' * 72
            print '# directories that are or will be empty:'
            emptyDirs.sort()
            for emptyDir in emptyDirs:
                generate_delete(emptyDir)


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
                for dirEntry in e.dirwalk():
                    #print '\n# adding dir ' + dirEntry.pathname
                    if not dirEntry.deleted:
                        for name, fileEntry in dirEntry.files.iteritems():
                            if not fileEntry.deleted:
                                self.add_entry(fileEntry)
                        dirEntry.finalize()
                        self.add_entry(dirEntry)
            maxd = e.max_depth()
            if self.maxDepth < maxd:
                self.maxDepth = maxd

    # Hashmap.add_entry
    def add_entry(self, entry):
        """Store a file or directory in the HashMap, indexed by it's
        hash.
        """

        if entry.hexdigest in self.contentHash:
            self.contentHash[entry.hexdigest].append(entry)
        else:
            self.contentHash[entry.hexdigest] = [ entry ]

        if entry.depth < self.minDepth:
            self.minDepth = entry.depth

    # Hashmap.display
    def display(self):
        """Generate a human readable report."""
        for hashval, list in self.contentHash.iteritems():
            for entry in list:
                entry.display(False, False)

    # Hashmap.delete
    def delete(self, entry):
        """Marks an entry as deleted then remove it from the HashMap"""

        entry.delete()

        # remove the entry from the hashmap
        list = self.contentHash[entry.hexdigest]
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

    # HashMap.prune
    def prune(self):
        """Removes deleted objects from the HashMap"""
        for hashval, list in self.contentHash.iteritems():
            newlist=[]
            for entry in list:
                if not entry.deleted:
                    newlist.append(entry)
            self.contentHash[hashval]=newlist

    # HashMap.resolve
    def resolve(self):
        """Compares all entries and where hash collisions exists, pick a
        keeper.
        """
        prevCount = self.allFiles.count_deleted()

        # no need to resolve uniques, so remove them from the HashMap
        singles=[]
        for hashval, list in self.contentHash.iteritems():
            if len(list) == 1:
                singles.append(hashval)
        for e in singles:
            del self.contentHash[e]

        # delete the directories first, in order of
        # increasing depth
        if verbosity > 0:
            print '# checking candidates from depth',
            print str(self.minDepth) + ' through ' + str(self.maxDepth)
        for currentDepth in xrange(self.minDepth-1,self.maxDepth+1):
            for hashval, list in self.contentHash.iteritems():
                example = list[0]
                if isinstance(example, DirObj):
                    win, losers = resolve_candidates(list, currentDepth)
                    if losers is not None:
                        for loser in losers:
                            if not loser.deleted:
                                if verbosity > 0:
                                    print '# dir "' + loser.pathname,
                                    print '" covered by "',
                                    print win.pathname + '"'
                                self.delete(loser)
                                loser.winner = win
                        self.prune()

        for hashval, list in self.contentHash.iteritems():
            example = list[0]
            if isinstance(example, FileObj):
                win, losers = resolve_candidates(list)
                for loser in losers:
                    if not loser.deleted:
                        if verbosity > 0:
                            print '# file "' + loser.pathname,
                            print '" covered by "' + win.pathname + '"'
                        self.delete(loser)
                        loser.winner = win

        return self.allFiles.count_deleted() - prevCount


class DirObj():
    """A directory object which can hold metadata and references to
    files and subdirectories.
    """
    def __init__(self, name, weightAdjust=0, parent=None):
        self.name = name
        self.files={}
        self.deleted = False
        self.winner = None
        self.subdirs={}
        self.weightAdjust = weightAdjust
        self.parent = parent
        ancestry = self.get_lineage()
        self.pathname='/'.join(ancestry)
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
        print self.hexdigest + ' ' + self.pathname

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

    # DirObj.generate_commands
    def generate_commands(self, selectDirMap, selectFileMap, emptyMap):
        """Generates delete commands to dedup all contents of this
        directory.
        """
        if self.deleted:
            if self.winner is not None:
                if self.winner.pathname in selectDirMap:
                    # use existing loser list:
                    loserList = selectDirMap[self.winner.pathname]
                    loserList.append(self.pathname)
                else:
                    # start a new loser list:
                    selectDirMap[self.winner.pathname] = [self.pathname]
            else:
                emptyMap[self.pathname]=True
        else:
            for fileName, fileEntry in self.files.iteritems():
                fileEntry.generate_commands(selectDirMap,
                                            selectFileMap,
                                            emptyMap)
            for dirName, subdir in self.subdirs.iteritems():
                subdir.generate_commands(selectDirMap,
                                            selectFileMap,
                                            emptyMap)

    # DirObj.is_empty
    def is_empty(self):
        """Checks if the dir is empty, ignoring items marked as deleted
        or ignored.
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
        digests=[]
        for filename, fileEntry in self.files.iteritems():
            digests.append(fileEntry.hexdigest)
        for dirname, dirEntry in self.subdirs.iteritems():
            digests.append(dirEntry.hexdigest)
        digests.sort()
        sha1 = hashlib.sha1()
        for d in digests:
            sha1.update(d)
        self.hexdigest = sha1.hexdigest()

    # DirObj.count_deleted_bytes
    def count_deleted_bytes(self):
        """returns a count of all the sizes of the deleted objects
        within.
        """
        bytes = 0
        for name, d in self.subdirs.iteritems():
            bytes = bytes + d.count_deleted_bytes()
        for name, f in self.files.iteritems():
            if f.deleted:
                bytes = bytes + f.count_deleted_bytes()
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
    def __init__(self, name, parent=None, dbTime=None,
                    db = None, weightAdjust = 0):
        self.name = name;
        self.winner = None
        self.parent = parent
        self.deleted = False
        self.weightAdjust = weightAdjust
        self.ignore = self.name in DELETE_LIST

        if self.parent is not None:
            ancestry = self.parent.get_lineage()
            self.pathname='/'.join(ancestry) + '/' + self.name
            self.depth = len(ancestry) + self.weightAdjust
        else:
            self.pathname = self.name
            self.depth = self.weightAdjust

        statResult = os.stat(self.pathname)
        self.modTime = statResult.st_mtime
        self.createTime = statResult.st_ctime
        self.bytes = statResult.st_size
        if self.bytes == 0:
            self.ignore = True
            # the sha1 digest of 0 bytes is fixed:
            self.hexdigest='da39a3ee5e6b4b0d3255bfef95601890afd80709'
            return

        if db is not None and self.pathname in db:
            # we've a cached hash value for this pathname
            if self.modTime > dbTime:
                # file is newer than db
                pass
            else:
                # db is newer than file
                if verbosity > 0:
					print '# ' + self.pathname + ' already in db'
                self.hexdigest = db[self.pathname]
                return

        # open and read the file
        sha1 = hashlib.sha1()
        with open(self.pathname, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
        self.hexdigest = sha1.hexdigest()

        if verbosity > 0:
			print '# computed new hash for ' + self.pathname

        if db is not None:
            # add/update the cached hash value for this entry:
            db[self.pathname]=self.hexdigest

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

    # FileObj.generate_commands
    def generate_commands(self, selectDirMap, selectFileMap, emptyMap):
        """Generates delete commands to dedup all contents"""
        if self.deleted and not self.ignore:
            if self.winner is not None:
                # just a trivial check to confirm hash matches:
                if self.bytes != self.winner.bytes:
                    print '# BIRTHDAY LOTTERY CRISIS!'
                    print '# matched hashes and mismatched sizes!'
                    sys.exit(-1)
                if self.winner.pathname in selectFileMap:
                    # use existing loserList
                    loserList = selectFileMap[self.winner.pathname]
                    loserList.append(self.pathname)
                else:
                    # create a new loserList
                    selectFileMap[self.winner.pathname]=[self.pathname]
            else:
                emptyMap[self.pathname] = True

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

    # FileObj.count_deleted_bytes
    def count_deleted_bytes(self):
        """Returns a count of all the sizes of the deleted objects
        within
        """
        if self.deleted:
             return self.bytes
        else:
            return 0

    # FileObj.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        if self.deleted:
             return 1
        else:
            return 0

def clean_database(databasePathname):
    """function to remove dead nodes from the hash db"""

    if dbm != 'gdbm':
        print '# non-gdbm databases dont support the reorganize method!'
        sys.exit(-1)

    print '# loading database ' + databasePathname
    try:
        db = gdbm.open(databasePathname, 'w')
    except: # TODO name the exception here
        print "# " + databasePathname + " could not be loaded"
        sys.exit(-1)

    # even though gdbm supports memory efficient iteration over
    # all keys, I want to order my traversal across similar
    # paths to leverage caching of directory files:
    allKeys = db.keys()
    print '# finished loaded keys from ' + databasePathname
    allKeys.sort()
    print '# finished sorting keys from ' + databasePathname
    print '# deleting dead nodes'
    count = 0
    for currKey in allKeys:
        try:
            os.stat(currKey)
        except OSError:
            del db[currKey]
            sys.stdout.write('*')
            count = count+1
        else:
            sys.stdout.write('.')
        sys.stdout.flush()
    print "\n# reorganizing " + databasePathname
    db.reorganize()
    db.sync()
    db.close()
    print '# done cleaning ' + databasePathname + ', removed',
    print str(count) + ' dead nodes!'

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
    args, paths = parser.parse_known_args()

    verbosity = args.verbosity
    databasePathname = args.database
    cleanDatabase = args.clean_database
    staggerPaths = args.stagger_paths

    if staggerPaths and cleanDatabase:
        print '# You probably did not mean to supply both -s and -c'
        print '# Paths are not processed when cleaning the hash database'
        sys.exit(-1)

    if databasePathname is not None:
        print '# set to use database: ' + databasePathname
        if cleanDatabase:
            clean_database(databasePathname)
            sys.exit(0)
    elif cleanDatabase:
        print '# database file must be specified for --clean-database',
        print 'command (use -d)'
        sys.exit(-1)

    allFiles = EntryList(paths, databasePathname, staggerPaths)
    passCount = 0
    # fake value to get the loop started:
    deleted = 1
    # while things are still being removed, keep working:
    while deleted > 0:

        h = HashMap(allFiles)
        deletedDirectories = allFiles.prune_empty()

        h = HashMap(allFiles)
        deletedHashMatches = h.resolve()

        deleted = deletedDirectories + deletedHashMatches
        passCount = passCount + 1
        if deleted > 0:
            print '# ' + str(deleted) + ' entries deleted on pass',
            print str(passCount)

    allFiles.generate_commands()

    #for e in allFiles.walk():
    #    e.display(False,False)
    endTime = time.time()
    print '# total bytes marked for deletion (not including',
    print 'directory files): ' + str(allFiles.count_deleted_bytes())
    print '# total running time: ' + str(endTime - startTime),
    print 'seconds.'

# vim: set expandtab sw = 4 ts = 4:
