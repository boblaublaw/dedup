# -*- coding: utf-8 -*-

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
    def __init__(self, args):
        self.args = args
        try:
            self.mod_time = os.stat(self.args.database).st_mtime
        except OSError:
            print("# db " + self.args.database + " doesn't exist yet")
            self.mod_time = time.time()
        print('# db last modification time is ' +
              str(time.time() - self.mod_time) + ' seconds ago')

        try:
            import gdbm
            self.db_type = 'gdbm'
        except ImportError:
            self.db_type = 'anydbm'
            print('# no gdbm implementation found, trying anydbm')
            try:
                import anydbm
            except ImportError:
                print('# no dbm implementation found!')
                sys.exit(-1)

        print('# set to use database ' +
              self.args.database + ' of type: ' + self.db_type)
        print('# loading database ' + self.args.database)
        try:
            if self.db_type == 'gdbm':
                self.db = gdbm.open(self.args.database, 'c')
            elif self.db_type == 'anydbm':
                self.db = anydbm.open(self.args.database, 'c')
        except:  # TODO name the exception here
            print("# " + self.args.database + " could not be loaded")
            sys.exit(-1)

    def lookup_hash(self, f):
        """look up this path to see if it has already been computed"""
        if f.abspathname in self.db:
            # we've a cached hash value for this abspathname
            if f.mod_time > self.mod_time:
                # file is newer than db
                pass
            else:
                # db is newer than file
                digest = self.db[f.abspathname]
                if self.args.verbosity > 0:
                    print('# hash ' + digest + ' for ' +
                          f.abspathname + ' already in db.')
                return digest
        digest = compute_hash(f.abspathname)
        # add/update the cached hash value for this entry:
        self.db[f.abspathname] = digest
        return digest

    def clean(self):
        """function to remove dead nodes from the hash db"""
        if self.db_type != 'gdbm':
            print('# non-gdbm databases (' + self.db_type +
                  ') dont support the reorganize method!')
            sys.exit(-1)

        start_time = time.time()
        print('# Starting database clean...')
        # even though gdbm supports memory efficient iteration over
        # all keys, I want to order my traversal across similar
        # paths to leverage caching of directory files:
        all_keys = self.db.keys()
        print('# finished loaded keys from ' + self.pathname)
        all_keys.sort()
        print('# finished sorting keys from ' + self.pathname)
        print('# deleting dead nodes')
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
        print("# reorganizing " + self.pathname)
        self.db.reorganize()
        self.db.sync()
        print('# done cleaning ' + self.pathname + ', removed ' +
              str(miss_count) + ' dead nodes and kept ' + str(hit_count) + ' nodes!')
        end_time = time.time()
        print('# Database clean complete after ' +
              str(end_time - start_time) + 'seconds')

# vim: set expandtab sw=4 ts=4:
