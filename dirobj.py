# -*- coding: utf-8 -*-

import os
import shutil
import hashlib

# CONSTANTS:
#
# Python doesn't really have constants so I'll use ALLCAPS to indicate
# that I do not expect these values to change. ¯\_(ツ)_/¯

DELETE_DIR_LIST = [
    ".git",
    ".svn",
    ".dropbox.cache",
    "__MACOSX"]

# This list describes files and directories we do not want to risk
# messing with.  If we encounter these, never mark them for deletion.
# TODO - implement this
DO_NOT_DELETE_LIST = []


class DirObj():
    """A directory object which can hold metadata and references to
    files and subdirectories.
    """

    def __init__(self, name, args, weight_adjust=0, parent=None):
        self.name = name
        self.args = args
        self.files = {}
        self.to_delete = False
        self.winner = None
        self.subdirs = {}
        self.weight_adjust = weight_adjust
        self.parent = parent
        ancestry = self.get_lineage()
        self.pathname = os.path.join(*ancestry)
        self.abspathname = os.path.abspath(self.pathname)
        self.abspathnamelen = len(self.abspathname)
        self.depth = len(ancestry) + self.weight_adjust


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
            for _, entry in self.subdirs.items():
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
    def place_dir(self, input_dir_name, weight_adjust):
        """Matches a pathname to a directory structure and returns a
        DirObj object.
        """
        input_dir_list = input_dir_name.split(os.path.sep)
        name_list = self.name.split(os.path.sep)

        while (len(input_dir_list) and len(name_list)):
            x = input_dir_list.pop(0)
            y = name_list.pop(0)
            if x != y:
                print('\nFATAL: ' + x + ' and ' + y +
                      ' do not match', file=sys.stderr)
                sys.exit(-1)
            if x in DELETE_DIR_LIST:
                return None

        if len(input_dir_list) == 0:
            return self

        next_dir_name = input_dir_list[0]
        if next_dir_name in self.subdirs:
            tmp_name = os.path.join(*input_dir_list)
            tmp_sub = self.subdirs[next_dir_name]
            return tmp_sub.place_dir(tmp_name, weight_adjust)

        next_dir = DirObj(next_dir_name, self.args, weight_adjust, self)
        self.subdirs[next_dir_name] = next_dir
        return next_dir.place_dir(os.path.join(*input_dir_list), weight_adjust)

    # DirObj.dirwalk
    def dirwalk(self, topdown=False):
        """A generator which traverses just subdirectories"""
        if topdown:
            yield self
        for _, d in self.subdirs.items():
            for dir_entry in d.dirwalk():
                yield dir_entry
        if not topdown:
            yield self

    # DirObj.delete
    def mark_for_delete(self):
        """Mark this directory and all children as deleted"""
        self.to_delete = True
        for _, d in self.subdirs.items():
            d.mark_for_delete()
        for _, f in self.files.items():
            f.mark_for_delete()

    # DirObj.generate_reports
    def generate_reports(self, reports):
        """Populates several "reports" that describe duplicated
        directories, files, as well as empty directories and files
        """
        dir_report = reports['directories']
        empty_report = reports['directories that are empty after reduction']
        started_empty_report = reports['directories that started empty']

        if self.to_delete:
            if self.winner is None:
                # this is a cheat wherein I use a magic value to designate
                # empty dirs
                if self.started_empty():
                    started_empty_report['___started_empty___'].append(self)
                else:
                    empty_report['___empty___'].append(self)
            else:
                loser_list = dir_report[self.winner.abspathname]
                loser_list.append(self)
        else:
            for _, file_entry in self.files.items():
                file_entry.generate_reports(reports)
            for _, subdir in self.subdirs.items():
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
        for _, file_entry in self.files.items():
            if not file_entry.to_delete:
                return False

        for _, subdir in self.subdirs.items():
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
            for _, dir_entry in self.subdirs.items():
                dir_entry.prune_empty()

    # DirObj.finalize
    def finalize(self):
        """Once no more files or directories are to be added, we can
        create a meta-hash of all the hashes therein.  This allows us to
        test for duplicate directories.
        """
        digests = []
        for _, file_entry in self.files.items():
            digests.append(file_entry.hexdigest)
        for _, dir_entry in self.subdirs.items():
            digests.append(dir_entry.hexdigest)
        digests.sort()
        #map(encode('utf-8'), digests)
        sha1 = hashlib.sha1()
        for d in digests:
            sha1.update(d.encode('utf-8'))
        self.hexdigest = sha1.hexdigest()
        if (len(self.files) + len(self.subdirs)) == 0:
            self.to_delete = not self.args.keep_empty_dirs

    # DirObj.count_bytes
    def count_bytes(self, to_delete=False):
        """returns a count of all the sizes of the deleted objects
        within.
        """
        bytes = 0
        for _, d in self.subdirs.items():
            bytes = bytes + d.count_bytes(to_delete)
        for _, f in self.files.items():
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
        for _, d in self.subdirs.items():
            to_delete = to_delete + d.count_deleted()
        for _, f in self.files.items():
            if f.to_delete:
                to_delete = to_delete + 1
        return to_delete

# vim: set expandtab sw=4 ts=4:
