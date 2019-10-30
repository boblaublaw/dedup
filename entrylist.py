#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import stat
from fileobj import FileObj
from dirobj import DirObj, DELETE_FILE_LIST, DELETE_DIR_LIST, DO_NOT_DELETE_LIST

def issocket(path):
    """For some reason python provides isfile and isdirectory but not
    issocket().
    """
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

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

class EntryList:
    """A container for all source directories and files to examine"""
    def __init__(self, paths, db, args):
        self.contents = {}
        self.db = db
        self.args = args
        stagger = 0

        # walk arguments adding files and directories
        for path in paths:
            # strip trailing slashes, they are not needed
            path = path.rstrip(os.path.sep)

            # check if a weight has been provided for this argument
            weightAdjust, entry = check_level(path)

            if os.path.isfile(path):
                if args.stagger_paths:
                    weightAdjust = weightAdjust + stagger
                newFile = FileObj(path, weightAdjust = weightAdjust)
                if args.stagger_paths:
                    stagger = stagger + newFile.depth
                self.contents[path] = newFile
            elif issocket(path):
                print '# Skipping a socket ' + entry
            elif os.path.isdir(path):
                if args.stagger_paths:
                    weightAdjust = weightAdjust + stagger
                topDirEntry = DirObj(path, self.args, weightAdjust)
                self.contents[path] = topDirEntry
                for dirName, subdirList, fileList in os.walk(path, topdown = False):
                    # we do not walk into or add names from our ignore list.  
                    # We wont delete them if they are leaf nodes and we wont 
                    # count them towards parent nodes.
                    if os.path.basename(dirName) in DELETE_DIR_LIST:
                        continue

                    dirEntry = topDirEntry.place_dir(dirName, weightAdjust)
                    if dirEntry is None:
                        continue

                    for fname in fileList:
                        pname = os.path.join(dirEntry.abspathname, fname)
                        if issocket(pname):
                            print '# Skipping a socket',
                            print pname
                        elif os.path.basename(fname) not in DELETE_FILE_LIST:
                            newFile = FileObj(fname, db,
                                            parent = dirEntry,
                                            weightAdjust = weightAdjust)
                            if newFile.bytes == 0 and not args.keep_empty_files:
                                newFile.deleted = True
                            dirEntry.files[fname]=newFile
                if args.stagger_paths:
                    stagger = topDirEntry.max_depth()
            else:
                print "I don't know what this is" + path
                sys.exit()

    # EntryList.testDeletes
    def test_deletes(self):
        for name, e in self.contents.iteritems():
            e.test_delete()

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
        if not self.args.keep_empty_dirs:
            for _, e in self.contents.iteritems():
                e.prune_empty()
        return self.count_deleted() - prevCount

# vim: set expandtab sw=4 ts=4: