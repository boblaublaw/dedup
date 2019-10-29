#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
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
    digest = sha1.hexdigest()
    return digest


class HashDbObj():
    def __init__(self, args):
        self.args = args
        try:
            self.modTime = os.stat(self.args.database).st_mtime
        except OSError:
            print "# db " + self.args.database + " doesn't exist yet"
            self.modTime = time.time()
        print '# db last modification time is',
        print str(time.time() - self.modTime) + ' seconds ago'

        try:
            import gdbm
            self.dbType = 'gdbm'
        except ImportError:
            self.dbType='anydbm'
            print '# no gdbm implementation found, trying anydbm'
            try:
                import anydbm
            except ImportError:
                print '# no dbm implementation found!'
                sys.exit(-1)
        print '# set to use database ' + self.args.database,
        print 'of type: ' + self.dbType

        print '# loading database ' + self.args.database
        try:
            if self.dbType == 'gdbm':
                self.db = gdbm.open(self.args.database, 'c')
            elif self.dbType == 'anydbm':
                self.db = anydbm.open(self.args.database, 'c')
        except: # TODO name the exception here
            print "# " + self.args.database + " could not be loaded"
            sys.exit(-1)

    def lookup_hash(self, f):
        """look up this path to see if it has already been computed"""
        if f.abspathname in self.db:
            # we've a cached hash value for this abspathname
            if f.modTime > self.modTime:
                # file is newer than db
                pass
            else:
                # db is newer than file
                digest = self.db[f.abspathname]
                if self.args.verbosity > 0:
                    print '# hash ' + digest + ' for ' + f.abspathname + ' already in db.'
                return digest
        digest=compute_hash(f.abspathname)
        # add/update the cached hash value for this entry:
        self.db[f.abspathname]=digest
        return digest

    def clean(self):
        """function to remove dead nodes from the hash db"""
        if self.dbType != 'gdbm':
            print '# non-gdbm databases (' + self.dbType + ') dont support the',
            print 'reorganize method!'
            sys.exit(-1)

        startTime = time.time()
        print '# Starting database clean...'
        # even though gdbm supports memory efficient iteration over
        # all keys, I want to order my traversal across similar
        # paths to leverage caching of directory files:
        allKeys = self.db.keys()
        print '# finished loaded keys from ' + self.pathname
        allKeys.sort()
        print '# finished sorting keys from ' + self.pathname
        print '# deleting dead nodes'
        misscount = 0
        hitcount = 0
        for currKey in allKeys:
            try:
                os.stat(currKey)
            except OSError:
                del self.db[currKey]
                if self.args.verbosity > 0:
                    sys.stdout.write('*')
                    sys.stdout.flush()
                misscount = misscount+1
            else:
                hitcount = hitcount + 1
                if self.args.verbosity > 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
        print "# reorganizing " + self.pathname
        self.db.reorganize()
        self.db.sync()
        print '# done cleaning ' + self.pathname + ', removed',
        print str(misscount) + ' dead nodes and kept ' + str(hitcount),
        print 'nodes!'
        endTime = time.time()
        print '# Database clean complete after ' + str(endTime - startTime),
        print 'seconds.\n'

# vim: set expandtab sw=4 ts=4: