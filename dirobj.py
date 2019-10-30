#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import hashlib

# CONSTANTS:
#
# Python doesn't really have constants so I'll use ALLCAPS to indicate
# that I do not expect these values to change. ¯\_(ツ)_/¯

# This list represents files that may linger in directories preventing
# this algorithm from recognizing them as empty.  we mark them as
# deletable, even if we do NOT have other copies available:

DELETE_FILE_LIST = [
    "album.dat",
    "album.dat.lock",
    "photos.dat",
    "photos.dat.lock",
    "Thumbs.db",
    ".lrprev",
    "Icon\r",
    ".DS_Store",
    "desktop.ini",
    ".dropbox.attr",
    ".typeAttributes.dict" ]

DELETE_DIR_LIST = [
    ".git",
    ".svn",
    ".dropbox.cache",
    "__MACOSX" ]
 
# This list describes files and directories we do not want to risk
# messing with.  If we encounter these, never mark them for deletion.
# TODO - implement this
DO_NOT_DELETE_LIST = []


class DirObj():
    """A directory object which can hold metadata and references to
    files and subdirectories.
    """
    def __init__(self, name, args, weightAdjust=0, parent=None):
        self.name = name
        self.args = args
        self.files = {}
        self.to_delete = False
        self.winner = None
        self.subdirs = {}
        self.weightAdjust = weightAdjust
        self.parent = parent
        ancestry = self.get_lineage()
        self.pathname = os.path.join(*ancestry)
        self.abspathname = os.path.abspath(self.pathname)
        self.abspathnamelen = len(self.abspathname)
        self.depth = len(ancestry) + self.weightAdjust

    # DirObj.testDelete
    def test_delete(self):
        # confirm that the pathname starts with "test"
        if self.to_delete:
            if self.pathname[:6] != "tests/":
                print 'something has gone catastrophically wrong in DirObj.test_delete'
                sys.exit(-1)
            else:
                print("# deleting dir " + self.pathname)
                shutil.rmtree(self.pathname)
        else:
            for _, s in self.subdirs.iteritems():
                s.test_delete()
            for _, f in self.files.iteritems():
                f.test_delete()

    # DirObj.get_lineage
    def get_lineage(self):
        """Crawls back up the directory tree and returns a list of
        parents.
        """
        if self.parent is None:
            return self.name.split(os.path.sep)
        ancestry = self.parent.get_lineage()
        ancestry.append(self.name)
        return ancestry

    # DirObj.max_depth
    def max_depth(self):
        """Determine the deepest point from this directory"""
        md = self.depth
        if len(self.subdirs.keys()):
            for _, entry in self.subdirs.iteritems():
                if not entry.to_delete:
                    td = entry.max_depth()
                    if td > md:
                        md = td
            return md
        elif len(self.files.keys()):
            return md + 1
        else:
            return md

    # DirObj.place_dir
    def place_dir(self, inputDirName, weightAdjust):
        """Matches a pathname to a directory structure and returns a
        DirObj object.
        """
        inputDirList = inputDirName.split(os.path.sep)
        nameList = self.name.split(os.path.sep)

        while (len(inputDirList) and len(nameList)):
            x = inputDirList.pop(0)
            y = nameList.pop(0)
            if x != y:
                print x + ' and ' + y + ' do not match'
                raise LookupError
            if x in DELETE_DIR_LIST:
                return None

        if len(inputDirList) == 0:
            return self

        nextDirName = inputDirList[0]
        if nextDirName in self.subdirs:
            tmpName= os.path.join(*inputDirList)
            tmpSub = self.subdirs[nextDirName]
            return tmpSub.place_dir(tmpName, weightAdjust)

        #print "did not find " + nextDirName + " in " + self.name
        nextDir = DirObj(nextDirName, self.args, weightAdjust, self)
        self.subdirs[nextDirName]=nextDir
        return nextDir.place_dir(os.path.join(*inputDirList), weightAdjust)

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

    # DirObj.delete
    def mark_for_delete(self):
        """Mark this directory and all children as deleted"""
        self.to_delete = True
        for _, d in self.subdirs.iteritems():
            d.mark_for_delete()
        for _, f in self.files.iteritems():
            f.mark_for_delete()

    # DirObj.generate_reports
    def generate_reports(self, reports):
        """Populates several "reports" that describe duplicated
        directories, files, as well as empty directories and files
        """
        dirReport = reports['directories']
        emptyReport = reports['directories that are empty after reduction']
        startedEmptyReport = reports['directories that started empty']

        if self.to_delete:
            if self.winner is None:
                # this is a cheat wherein I use a magic value to designate 
                # empty dirs
                if self.started_empty():
                    startedEmptyReport['___started_empty___'].append(self)
                else:
                    emptyReport['___empty___'].append(self)
            else:
                loserList = dirReport[self.winner.abspathname]
                loserList.append(self)
        else:
            for fileName, fileEntry in self.files.iteritems():
                fileEntry.generate_reports(reports)
            for dirName, subdir in self.subdirs.iteritems():
                subdir.generate_reports(reports)

    # DirObj.started_empty
    def started_empty(self):
        """Checks if the dir was empty when the program was
        invoked.  If we see ignored items, we ignore them.
        """
        if (len(self.subdirs) + len(self.files)) == 0:
            return True
        return False

    # DirObj.is_empty
    def is_empty(self):
        """Checks if the dir is currented marked as empty, ignoring 
        items marked as deleted or ignored.  (In other words, 
        ignored items won't protect a directory from being marked 
        for deletion.)
        """
        for fileName, fileEntry in self.files.iteritems():
            if not fileEntry.to_delete:
                return False

        for dirName, subdir in self.subdirs.iteritems():
            if not subdir.to_delete and not subdir.is_empty():
                return False

        return True

    # DirObj.prune_empty
    def prune_empty(self):
        """Crawls through all directories and marks the shallowest
        empty entries for deletion.
        """
        if (self.is_empty()
                and not self.to_delete
                and self.parent is None):
            self.mark_for_delete()
        elif (self.is_empty()
                and not self.to_delete
                and self.parent is not None
                and not self.parent.is_empty()):
            self.mark_for_delete()
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
        if (len(self.files) + len(self.subdirs)) == 0:
            self.to_delete = not self.args.keep_empty_dirs

    # DirObj.count_bytes
    def count_bytes(self, to_delete=False):
        """returns a count of all the sizes of the deleted objects
        within.
        """
        bytes = 0
        for name, d in self.subdirs.iteritems():
            bytes = bytes + d.count_bytes(to_delete)
        for name, f in self.files.iteritems():
            if f.to_delete and to_delete:
                bytes = bytes + f.count_bytes(to_delete)
            elif not f.to_delete and not to_delete:
                bytes = bytes + f.count_bytes(to_delete)
        return bytes

    # DirObj.count_deleted
    def count_deleted(self):
        """returns a count of all the deleted objects within"""
        if self.to_delete:
            to_delete = 1
        else:
            to_delete = 0
        for name, d in self.subdirs.iteritems():
            to_delete = to_delete + d.count_deleted()
        for name, f in self.files.iteritems():
            if f.to_delete:
                to_delete = to_delete + 1
        return to_delete

# vim: set expandtab sw=4 ts=4: