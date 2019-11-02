# -*- coding: utf-8 -*-

"""
    This module describes the HashDbObj and helper functions
"""

import os
import sys
import hashlib
import time

# CONSTANTS:
#
# Python doesn't really have constants so I'll use ALLCAPS to indicate
# that I do not expect these values to change. ¯\_(ツ)_/¯

# size of hashing buffer:
BUF_SIZE = 65536


def compute_hash(pathname):
    """reads a file and computes a SHA1 hash"""
    # open and read the file

    # TODO - parameterize this to optionally check less
    #   than the whole file.

    sha1 = hashlib.sha1()
    with open(pathname, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


class HashDbObj():
    """
    The HashDbObj is a wrapper for a "dbm" cache file.
    This object is used if the "-d" option is requested at invocation.
    Two types of gdm caches are attempted, if neither is available, we fail.
    """
    def __init__(self, args, outfile):
        self.args = args
        self.outfile = outfile
        try:
            self.mod_time = os.stat(self.args.database).st_mtime
        except OSError:
            print("# db " + self.args.database +
                  " doesn't exist yet", file=self.outfile)
            self.mod_time = time.time()
        print('# db last modification time is ' +
              str(time.time() - self.mod_time) + ' seconds ago', file=self.outfile)

        try:
            import gdbm
            self.db_type = 'gdbm'
        except ImportError:
            self.db_type = 'anydbm'
            print('# no gdbm implementation found, trying anydbm', file=self.outfile)
            try:
                import anydbm
            except ImportError:
                print('\nFATAL: no dbm implementation found!', file=sys.stderr)
                sys.exit(-1)

        print('# set to use database ' +
              self.args.database + ' of type: ' + self.db_type, file=self.outfile)
        print('# loading database ' + self.args.database, file=self.outfile)
        try:
            if self.db_type == 'gdbm':
                self.db = gdbm.open(self.args.database, 'c')
            elif self.db_type == 'anydbm':
                self.db = anydbm.open(self.args.database, 'c')
        except ModuleNotFoundError:
            print("\nFATAL: " + self.args.database +
                  " could not be loaded", file=sys.stderr)
            sys.exit(-1)

    def lookup_hash(self, f):
        """look up this path to see if it has already been computed"""
        if f.pathname in self.db:
            # we've a cached hash value for this pathname
            if f.mod_time > self.mod_time:
                # file is newer than db
                pass
            else:
                # db is newer than file
                digest = self.db[f.pathname]
                if self.args.verbosity > 0:
                    print('# hash ' + digest + ' for ' +
                          f.pathname + ' already in db.', file=self.outfile)
                return digest
        digest = compute_hash(f.pathname)
        # add/update the cached hash value for this entry:
        self.db[f.pathname] = digest
        return digest

    def clean(self):
        """function to remove dead nodes from the hash db"""
        if self.db_type != 'gdbm':
            print('\nFATAL: non-gdbm databases (' + self.db_type +
                  ') dont support the reorganize method!', file=sys.stderr)
            sys.exit(-1)

        start_time = time.time()
        print('# Starting database clean...', file=self.outfile)
        # even though gdbm supports memory efficient iteration over
        # all keys, I want to order my traversal across similar
        # paths to leverage caching of directory files:
        all_keys = self.db.keys()
        print('# finished loaded keys from ' +
              self.args.database, file=self.outfile)
        all_keys.sort()
        print('# finished sorting keys from ' +
              self.args.database, file=self.outfile)
        print('# deleting dead nodes', file=self.outfile)
        miss_count = 0
        hit_count = 0
        for curr_key in all_keys:
            try:
                os.stat(curr_key)
            except OSError:
                del self.db[curr_key]
                if self.args.verbosity > 0:
                    sys.stdout.write('*')
                    sys.stdout.flush()
                miss_count = miss_count+1
            else:
                hit_count = hit_count + 1
                if self.args.verbosity > 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
        print("# reorganizing " + self.args.database, file=self.outfile)
        self.db.reorganize()
        self.db.sync()
        print('# done cleaning ' + self.args.database + ', removed ' +
              str(miss_count) + ' dead nodes and kept ' + str(hit_count) +
              ' nodes!', file=self.outfile)
        end_time = time.time()
        print('# Database clean complete after ' +
              str(end_time - start_time) + 'seconds', file=self.outfile)

# vim: set expandtab sw=4 ts=4:
