# -*- coding: utf-8 -*-

#from __future__ import print_function
from collections import defaultdict
from operator import attrgetter
from fileobj import FileObj
from dirobj import DirObj


def member_is_type(tup, typ):
    """for checking the type of a list member which is also packed in a
    tuple. This function assumes all list members are the same type.
    """
    l = tup[1]
    return isinstance(l[0], typ)


class HashMap:
    """A wrapper to a python dict with some helper functions"""

    def __init__(self, all_files, args):
        self.content_hash = defaultdict(lambda: [])
        self.min_depth = 1
        self.max_depth = 0
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
        if len(candidates) == 0:
            return

        candidates.sort(
            key=attrgetter('depth', 'abspathnamelen', 'abspathname'),
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
                    if self.args.verbosity > 0:
                        s = '# dir  "'
                        if isinstance(candidate, DirObj):
                            s = s + candidate.abspathname
                        else:
                            s = s + candidate.abspathname
                        print(s + '" covered by "' + winner.abspathname + '"')
                    candidate.winner = winner

    # HashMap.resolve
    def resolve(self):
        """Compares all entries and where hash collisions exists, pick a
        keeper.
        """
        prev_count = self.all_files.count_deleted()

        # no need to resolve uniques, so remove them from the HashMap
        uniques = []
        # you cannot modify a collection while iterating over it...
        for hashval, l in self.content_hash.items():
            if len(l) == 1:
                uniques.append(hashval)
        # ... so delete entries in a second pass.
        for entry in uniques:
            del self.content_hash[entry]

        # delete the directories first, in order of (de/in)creasing depth,
        # depending on the reverse_selection setting.
        #
        # This approach isn't strictly required but it results in fewer
        # calls to this function if we delete leaf nodes first, as it will
        # allow non-leaf directories to match on subsequent calls to
        # resolve().

        depths = range(self.min_depth - 1, self.max_depth + 1)
        if self.args.reverse_selection:
            depths = reversed(depths)

        if self.args.verbosity > 0:
            print('# checking candidates in dir depth order: ' + str(depths))

        for depth_filter in depths:
            # print '# checking depth ' + str(depth_filter)
            for hashval, candidates in filter(lambda x:
                                              member_is_type(x, DirObj), self.content_hash.items()):
                if self.args.reverse_selection:
                    maybes = [x for x in candidates if x.depth < depth_filter]
                else:
                    maybes = [x for x in candidates if x.depth > depth_filter]
                if len(maybes) > 0:
                    self.resolve_candidates(maybes)
            self.prune()

        for hashval, candidates in filter(lambda x: member_is_type(x, FileObj), self.content_hash.items()):
            self.resolve_candidates(candidates)
        self.prune()

        return self.all_files.count_deleted() - prev_count

# vim: set expandtab sw=4 ts=4:
