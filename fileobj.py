# -*- coding: utf-8 -*-

import os
import sys
from hashdbobj import compute_hash


class FileObj():
    """A file object which stores some metadata"""

    def __init__(self, name, args, db, parent=None, weight_adjust=0):
        self.name = name
        self.args = args
        self.db = db
        self.winner = None
        self.parent = parent
        self.weight_adjust = weight_adjust

        if self.parent is not None:
            ancestry = self.parent.get_lineage()
            ancestry.append(self.name)
            self.pathname = os.path.join(*ancestry)
            self.depth = len(ancestry) + self.weight_adjust
        else:
            self.pathname = self.name
            self.depth = self.weight_adjust

        self.abspathname = os.path.abspath(self.pathname)
        self.abspathnamelen = len(self.abspathname)

        stat_result = os.stat(self.abspathname)
        self.mod_time = stat_result.st_mtime
        self.create_time = stat_result.st_ctime
        self.bytes = stat_result.st_size

        if self.db is not None:
            self.hexdigest = self.db.lookup_hash(self)
        else:
            self.hexdigest = compute_hash(self.abspathname)
        self.to_delete = False

    # FileObj.max_depth
    def max_depth(self):
        return self.depth

    # FileObj.delete
    def mark_for_delete(self):
        """Mark for deletion"""
        self.to_delete = True

    # FileObj.generate_reports
    def generate_reports(self, reports):
        file_report = reports['files']
        empty_report = reports['empty files']
        """Generates delete commands to dedup all contents"""
        if not self.to_delete:
            return
        # this is a cheat wherein I use the empty_report as a list of keys
        # and I disregard the values
        if self.winner is None:
            empty_report['___empty___'].append(self)
            return
        # just a trivial check to confirm hash matches:
        if self.bytes != self.winner.bytes:
            print('\nFATAL: BIRTHDAY LOTTERY CRISIS!', file=sys.stderr)
            print('FATAL: matched hashes and mismatched sizes!', file=sys.stderr)
            sys.exit(-1)
        loser_list = file_report[self.winner.abspathname]
        loser_list.append(self)

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
