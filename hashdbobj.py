# -*- coding: utf-8 -*-

"""
    This module describes the HashDbObj and helper functions
"""

import os
import sys
import hashlib
import time
import dbm

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

        print('# loading database ' + self.args.database, file=self.outfile)
        try:
            self.db = dbm.open(self.args.database, 'c')
        except:
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

# vim: set expandtab sw=4 ts=4:
