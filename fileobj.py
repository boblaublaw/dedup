#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from hashdbobj import compute_hash

class FileObj():
    """A file object which stores some metadata"""
    def __init__(self, name, db, parent=None, weightAdjust = 0):
        self.name = name
        self.db = db
        self.winner = None
        self.parent = parent
        self.weightAdjust = weightAdjust

        if self.parent is not None:
            ancestry = self.parent.get_lineage()
            ancestry.append(self.name)
            self.pathname = os.path.join(*ancestry)
            self.depth = len(ancestry) + self.weightAdjust
        else:
            self.pathname = self.name
            self.depth = self.weightAdjust

        self.abspathname = os.path.abspath(self.pathname)
        self.abspathnamelen = len(self.abspathname)

        statResult = os.stat(self.abspathname)
        self.modTime = statResult.st_mtime
        self.createTime = statResult.st_ctime
        self.bytes = statResult.st_size

        if self.db is not None:
            self.hexdigest = self.db.lookup_hash(self)
        else:
            self.hexdigest = compute_hash(self.abspathname)
        self.to_delete = False

    # FileObj.test_delete
    # TODO increase protections against mistakes here
    def test_delete(self):
        if self.to_delete:
            print("# deleting file " + self.pathname)
            if self.pathname[:6] != "tests/":
                print 'something has gone catastrophically wrong in FileObj.test_delete'
                sys.exit(-1)
            os.remove(self.pathname)

    # FileObj.max_depth
    def max_depth(self):
        return self.depth

    # FileObj.delete
    def mark_for_delete(self):
        """Mark for deletion"""
        self.to_delete = True

    # FileObj.generate_reports
    def generate_reports(self, reports):
        fileReport = reports['files']
        emptyReport = reports['empty files']
        """Generates delete commands to dedup all contents"""
        if not self.to_delete:
            return
        # this is a cheat wherein I use the emptyReport as a list of keys
        # and I disregard the values
        if self.winner is None:
            emptyReport['___empty___'].append(self)
            return
        # just a trivial check to confirm hash matches:
        if self.bytes != self.winner.bytes:
            print '# BIRTHDAY LOTTERY CRISIS!'
            print '# matched hashes and mismatched sizes!'
            sys.exit(-1)
        loserList = fileReport[self.winner.abspathname]
        loserList.append(self)

    # FileObj.prune_empty
    def prune_empty(self):
        """Crawls through all directories and deletes the children of
        the deleted
        """
        return False            # can't prune a file

    # FileObj.count_bytes
    def count_bytes(self, to_delete=False):
        """Returns a count of all the sizes of the deleted objects
        within
        """
        if self.to_delete and to_delete:
             return self.bytes
        elif not self.to_delete and not to_delete:
            return self.bytes
        return 0 

    # FileObj.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        if self.to_delete:
             return 1
        else:
            return 0

# vim: set expandtab sw=4 ts=4: