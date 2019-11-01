# -*- coding: utf-8 -*-

import os
import stat
from fileobj import FileObj
from dirobj import DirObj, DELETE_DIR_LIST

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
    ".typeAttributes.dict"]


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
        first_part = parts.pop(0)
        remainder = ':'.join(parts)
        if check_int(first_part):
            return int(first_part), remainder
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
            weight_adjust, entry = check_level(path)

            if os.path.isfile(path):
                if args.stagger_paths:
                    weight_adjust = weight_adjust + stagger
                new_file = FileObj(path, args, weight_adjust=weight_adjust)
                if args.stagger_paths:
                    stagger = stagger + new_file.depth
                self.contents[path] = new_file
            elif issocket(path):
                print('WARNING: Skipping a socket ' + entry, file=sys.stderr)
            elif os.path.isdir(path):
                if args.stagger_paths:
                    weight_adjust = weight_adjust + stagger
                top_dir_entry = DirObj(path, self.args, weight_adjust)
                self.contents[path] = top_dir_entry
                for dir_name, _, file_list in os.walk(path, topdown=False):
                    # we do not walk into or add names from our ignore list.
                    # We wont delete them if they are leaf nodes and we wont
                    # count them towards parent nodes.
                    if os.path.basename(dir_name) in DELETE_DIR_LIST:
                        continue

                    dir_entry = top_dir_entry.place_dir(
                        dir_name, weight_adjust)
                    if dir_entry is None:
                        continue

                    for fname in file_list:
                        pname = os.path.join(dir_entry.abspathname, fname)
                        if issocket(pname):
                            print('WARNING: Skipping a socket ' +
                                  pname, file=sys.stderr)
                        elif os.path.basename(fname) not in DELETE_FILE_LIST:
                            new_file = FileObj(fname, args, db,
                                               parent=dir_entry,
                                               weight_adjust=weight_adjust)
                            if new_file.bytes == 0 and not args.keep_empty_files:
                                new_file.to_delete = True
                            dir_entry.files[fname] = new_file
                if args.stagger_paths:
                    stagger = top_dir_entry.max_depth()
            else:
                print("\nFATAL ERROR: dont know what this is: " +
                      path, file=sys.stderr)
                sys.exit()

    # EntryList.testDeletes
    def test_deletes(self):
        for _, e in self.contents.items():
            e.test_delete()

    # EntryList.count_bytes
    def count_bytes(self, deleted=False):
        """Returns a btyecount of all the (deleted) objects within"""
        bytes = 0
        for _, e in self.contents.items():
            bytes = bytes + e.count_bytes(deleted)
        return bytes

    # EntryList.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        count = 0
        for _, e in self.contents.items():
            count = count + e.count_deleted()
        return count

    # EntryList.prune_empty
    def prune_empty(self):
        """Flags all the children of the deleted objects within to also
        be deleted.
        """
        prev_count = self.count_deleted()
        if not self.args.keep_empty_dirs:
            for _, e in self.contents.items():
                e.prune_empty()
        return self.count_deleted() - prev_count

# vim: set expandtab sw=4 ts=4:
