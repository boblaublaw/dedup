# -*- coding: utf-8 -*-

"""
    This module is for the HashMap class (and a static helper)
"""

import sys
from collections import defaultdict
import operator
from fileobj import FileObj
from dirobj import DirObj


def member_is_type(tup, typ):
    """
    for checking the type of a list member which is also packed in a
    tuple. This function assumes all list members are the same type.
    """
    l = tup[1]
    return isinstance(l[0], typ)


class HashMap:
    """
    A wrapper to a python dict with some helper functions.
    This object is a hash-centric view of the filesystem. 
    Duplicate files and directories are represented here, indexed by its hash value.
    """
    def __init__(self, all_files, args, outfile=sys.stdout):
        self.content_hash = defaultdict(lambda: [])
        self.min_depth = 1
        self.max_depth = 0
        self.outfile = outfile
        # we will use this later to count deletions:
        self.all_files = all_files
        # reference to launch instructions
        self.args = args

        for _, e in all_files.contents.items():
            if isinstance(e, FileObj):
                self.add_entry(e)
            else:
                for dir_entry in filter(
                        lambda x: x.to_delete is False,
                        e.dirwalk()):
                    for _, file_entry in filter(
                            lambda x: x[1].to_delete is False,
                            dir_entry.files.items()):
                        self.add_entry(file_entry)
                    dir_entry.finalize()
                    self.add_entry(dir_entry)
            maxd = e.max_depth()
            if self.max_depth < maxd:
                self.max_depth = maxd

    # HashMap.add_entry
    def add_entry(self, entry):
        """Store a file or directory in the HashMap, indexed by it's
        hash, and then further appended to a list of other entries
        with the same hash.
        """
        self.content_hash[entry.hexdigest].append(entry)
        if entry.depth < self.min_depth:
            self.min_depth = entry.depth

    # HashMap.prune
    def prune(self):
        """Removes deleted objects from the HashMap"""
        delete_list = []
        for hashval, l in self.content_hash.items():
            trimmed_list = []
            for entry in l:
                if entry.to_delete:
                    entry.mark_for_delete()
                else:
                    trimmed_list.append(entry)
            # store the trimmed list
            if len(trimmed_list) > 0:
                self.content_hash[hashval] = trimmed_list
            else:
                # if no more entries exist for this hashval,
                # remove the entry from the dict:
                delete_list.append(hashval)

        # remove deleted items from the hash lookup dict:
        for entry in delete_list:
            del self.content_hash[entry]

    # HashMap.resolve_candidates
    def resolve_candidates(self, candidates):
        """Helper function which examines a list of candidate objects with
        identical contents (as determined elsewhere) to determine which of
        the candidates is the "keeper" (or winner).  The other candidates
        are designated losers.  The winner is selected by comparing the
        depths of the candidates.  If reverse_selection is true, the deepest
        candidate is chosen, else the shallowest is chosen.  In the case
        of a tie, the length of the full path is compared.
        """
        candidates.sort(
            key=operator.attrgetter('depth', 'pathnamelen', 'pathname'),
            reverse=self.args.reverse_selection)
        winner = candidates.pop(0)

        if isinstance(winner, DirObj) and winner.is_empty():
            # we trim empty directories using DirObj.prune_empty()
            # because it produces less confusing output
            return

        if isinstance(winner, FileObj) and winner.bytes == 0:
            # we also trim empty files
            return

        # once we have a winner, mark all the other candidates as losers
        for candidate in candidates:
            if candidate != winner:
                if not candidate.to_delete:
                    candidate.mark_for_delete()
                    candidate.winner = winner

    # HashMap.resolve
    def resolve(self):
        """Compares all entries and where hash collisions exists, pick a
        keeper.
        """
        prev_deleted = self.all_files.count_deleted()

        # do away with hash values that have no duplicates:
        self.content_hash = {k: v for k, v in self.content_hash.items() if len(v) != 1}

        for _, candidates in self.content_hash.items():
            self.resolve_candidates(candidates)

        self.prune()

        return self.all_files.count_deleted() - prev_deleted

# vim: set expandtab sw=4 ts=4:
