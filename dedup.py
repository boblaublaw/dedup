#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import stat
import time
import argparse
import shutil
from itertools import chain
from collections import defaultdict
from hashmap import HashMap
from hashdbobj import HashDbObj
from fileobj import FileObj
from dirobj import DirObj, DELETE_FILE_LIST, DELETE_DIR_LIST, DO_NOT_DELETE_LIST

# what to export when other scripts import this module:
#__all__ = ["FileObj", "DirObj", "EntryObj", "HashDbObj" ]

def sizeof_fmt(num, suffix='B'):
    """helper function found on stackoverflow"""
    prefixlist = ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']
    for unit in prefixlist:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

# for test coverage we calculate a value then throw it away:
ignore_val = sizeof_fmt(pow(1024,8))

def issocket(path):
    """For some reason python provides isfile and isdirectory but not
    issocket().
    """
    mode = os.stat(path).st_mode
    return stat.S_ISSOCK(mode)

def generate_delete(filename):
    """generates not-quite-safe rm commands.  TODO does not handle
    pathnames which contain both the ' and " characters.
    """
    # characters that we will wrap with double quotes:
    delimTestChars = set("'()")
    if any((c in delimTestChars) for c in filename):
        print 'rm -rf "' + filename + '"'
    else:
        print "rm -rf '" + filename + "'"

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
        firstPart = parts.pop(0)
        remainder = ':'.join(parts)
        if check_int(firstPart):
            return int(firstPart), remainder

    # if anything goes wrong just fail back to assuming the whole
    # thing is a path without a weight prefix.
    return 0, pathname

def synthesize_report(report):
    winnerList = []
    allMarkedBytes = 0
    allMarkedCount = 0
    for winnerName, loserList in report.iteritems():
        markedCount = len(loserList)
        allMarkedCount = allMarkedCount + markedCount
        totalMarkedBytes = 0
        if markedCount > 0:
            loserList.sort(key=lambda x: x.abspathname)
            for loser in loserList:
                totalMarkedBytes = totalMarkedBytes + loser.count_bytes(True)
        allMarkedBytes = allMarkedBytes + totalMarkedBytes
        newResult = {}
        newResult['winnerName'] = winnerName
        newResult['markedCount'] = markedCount
        newResult['totalMarkedBytes'] = totalMarkedBytes
        newResult['loserList'] = loserList
        winnerList.append( newResult )

    # set the order to present each result from this report:
    winnerList.sort(key=lambda x: x['totalMarkedBytes'], reverse=True)
    return winnerList, allMarkedBytes, allMarkedCount

def synthesize_reports(reportMap):
    reportList=[]
    for reportName, report in reportMap.iteritems():
        newReport={}
        newReport['reportName']=reportName
        newReport['winnerList'], newReport['totalMarkedBytes'], newReport['markedCount'] = synthesize_report(report)
        reportList.append(newReport)
    
    reportList.sort(key=lambda x: x['totalMarkedBytes'], reverse=True)
    return reportList

def generate_map_commands(report, emptyReportNames):
    winnerList = report['winnerList']
    winCount = len(winnerList)
    # dont generate empty sections
    if winCount == 0:
        return
    reportName = report['reportName']
    totalMarkedBytes = report['totalMarkedBytes']
    markedCount = report['markedCount']

    print "\n" + '#' * 72
    if reportName in emptyReportNames:
        print '# ' + reportName + ': ' + str(markedCount) + ' to remove'
        print '# This section could make ' + sizeof_fmt(totalMarkedBytes) + ' of file data redundant\n'
    else:
        print '# ' + reportName + ': ' + str(winCount),
        print 'to keep and ' + str(markedCount) + ' to remove'
        print '# This section could make ' + sizeof_fmt(totalMarkedBytes) + ' of file data redundant\n'

    for winner in winnerList:
        print "# This subsection could save " + sizeof_fmt(winner['totalMarkedBytes'])
        if reportName not in emptyReportNames:
            print "#      '" + winner['winnerName'] + "'" 
        for loser in winner['loserList']:
            generate_delete(loser.abspathname)
        print

class EntryList:
    """A container for all source directories and files to examine"""

    def __init__(self, paths, db, args):
        self.contents = {}
        self.db = db
        self.args = args
        stagger = 0

        # walk arguments adding files and directories
        for entry in paths:
            # strip trailing slashes, they are not needed
            entry = entry.rstrip(os.path.sep)

            # check if a weight has been provided for this argument
            weightAdjust, entry = check_level(entry)

            if os.path.isfile(entry):
                if args.stagger_paths:
                    weightAdjust = weightAdjust + stagger
                newFile = FileObj(entry, weightAdjust = weightAdjust)
                if args.stagger_paths:
                    stagger = stagger + newFile.depth
                self.contents[entry] = newFile
            elif issocket(entry):
                print '# Skipping a socket ' + entry
            elif os.path.isdir(entry):
                if args.stagger_paths:
                    weightAdjust = weightAdjust + stagger
                topDirEntry = DirObj(entry, self.args, weightAdjust)
                self.contents[entry] = topDirEntry
                for dirName, subdirList, fileList in os.walk(entry,
                                                        topdown = False):
                    # we do not walk into or add names from our ignore list.  
                    # We wont delete them if they are leaf nodes and we wont 
                    # count them towards parent nodes.
                    if os.path.basename(dirName) in DELETE_DIR_LIST: 
                        continue

                    dirEntry = topDirEntry.place_dir(dirName, weightAdjust)
                    if dirEntry is None:
                        continue

                    for fname in fileList:
                        pname = os.path.join(dirEntry.abspathname, fname)
                        if issocket(pname):
                            print '# Skipping a socket',
                            print pname
                        elif os.path.basename(fname) not in DELETE_FILE_LIST:
                            newFile = FileObj(fname, db,
                                            parent = dirEntry,
                                            weightAdjust = weightAdjust)
                            if newFile.bytes == 0 and not args.keep_empty_files:
                                newFile.deleted = True
                            dirEntry.files[fname]=newFile
                if args.stagger_paths:
                    stagger = topDirEntry.max_depth()
            else:
                print "I don't know what this is" + entry
                sys.exit()

    # EntryList.count_bytes
    def count_bytes(self, deleted=False):
        """Returns a btyecount of all the (deleted) objects within"""
        bytes = 0
        for name, e in self.contents.iteritems():
            bytes = bytes + e.count_bytes(deleted)
        return bytes

    # EntryList.count_deleted
    def count_deleted(self):
        """Returns a count of all the deleted objects within"""
        count = 0
        for name, e in self.contents.iteritems():
            count = count + e.count_deleted()
        return count

    # EntryList.prune_empty
    def prune_empty(self):
        """Flags all the children of the deleted objects within to also
        be deleted.
        """
        prevCount = self.count_deleted()
        if not self.args.keep_empty_dirs:
            for _, e in self.contents.iteritems():
                e.prune_empty()
        return self.count_deleted() - prevCount

# jacked from SO:
#   https://stackoverflow.com/questions/229186/os-walk-without-digging-into-directories-below
def walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]

def run_tests():
    # walk all the dirs under 'tests' dir:
    # TODO - should probably look at the script location instead of PWD
    for dirName, subdirList, fileList in walklevel('tests', 0):
        for testName in subdirList:
            if (-1 == run_test(testName)):
                return -1
    return 0

def run_test(testName):
    print 'running test', testName
    testDir = 'tests' + os.path.sep + testName + os.path.sep + 'test'
    beforeDir = 'tests' + os.path.sep + testName + os.path.sep + 'before'
    afterDir = 'tests' + os.path.sep + testName + os.path.sep + 'after'
    print testDir #, beforeDir, afterDir
    # unconditonally remove tests/${testName}/test
    shutil.rmtree(testDir, ignore_errors=True)
    # copy tests/${testName}/before to tests/${testName}/test
    shutil.copytree(beforeDir, testDir, symlinks=False, ignore=None)
    # pull arguments out of tests/${testName}/args.json(?)

    # dedup tests/${testName}/test

    # compare tests/${testName}/test with tests/${testName}/after
    # use "diff --recursive --brief"
    return 0

# each command line invocation runs main once.
# the run_tests() test harness will run main() several times.
def main(args, paths):
    if args.clean_database and db is None:
        print '# database file must be specified for --clean-database',
        print 'command (use -d)'
        return(-1)

    if len(paths) == 0 and args.stagger_paths:
        print '# -s/--stagger-paths specified, but no paths provided!'
        return(-1)

    db = None
    if args.database is not None:
        db=HashDbObj(args)

    if args.clean_database:
        db.clean()

    if len(paths) > 0:
        allFiles = EntryList(paths, db, args)
        passCount = 0
        # fake value to get the loop started:
        deleted = 1
        # while things are still being removed, keep working:
        while deleted > 0:
            sys.stdout.flush()
            h = HashMap(allFiles, args)
            deletedDirectories = allFiles.prune_empty()

            h = HashMap(allFiles, args)
            deletedHashMatches = h.resolve()

            deleted = deletedDirectories + deletedHashMatches
            passCount = passCount + 1
            if deleted > 0:
                print '# ' + str(deleted) + ' entries deleted on pass',
                print str(passCount)

        # a list of report names we will generate.  Note that these are later
        # indexed elsewhere, so be careful renaming
        regularReportNames = [ 'directories', 'files' ]
        emptyReportNames = [ 'directories that are empty after reduction',
                        'directories that started empty', 'empty files' ]

        # create each category for files to delete in its own report.
        # reports are a dict indexed by "winner" that points to a metadata
        # and a list of losers
        reportMaps={}
        for reportName in chain(regularReportNames, emptyReportNames):
            reportMaps[reportName] = defaultdict(lambda: [])

        for name, e in allFiles.contents.iteritems():
            e.generate_reports(reportMaps)

        reportLists = synthesize_reports(reportMaps)

        for report in reportLists:
            generate_map_commands(report, emptyReportNames)

        endTime = time.time()
        print '\n# total file data bytes marked for deletion',
        print sizeof_fmt(allFiles.count_bytes(deleted=True))
        print '# total dedup running time: ' + str(endTime - startTime),
        print 'seconds.'
    return 0

if __name__ == '__main__':
    startTime = time.time()
    desc="generate commands to eliminate redundant files and directories"
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                    help="increase output verbosity")
    parser.add_argument("-d", "--database", 
                    help="name of DBM file to use for hash cache")
    parser.add_argument("-c", "--clean-database", action="store_true",
                    help="clean hash cache instead of normal operation")
    parser.add_argument("-s", "--stagger-paths", action="store_true",
                    help="always prefer files in argument order")
    parser.add_argument("-r", "--reverse-selection", action="store_true",
                    help="reverse the dir/file selection choices")
    parser.add_argument("-t", "--run-tests", action="store_true",
                    help="run all the tests listed in 'test' subdir")
    parser.add_argument("-f", "--keep-empty-files", action="store_true",
                    help="do not delete empty files (default to false)")
    parser.add_argument("-e", "--keep-empty-dirs", action="store_true",
                    help="do not delete empty directories (default to false)")
    args, paths = parser.parse_known_args()

    # requesting unit test execution discards all other options.
    if args.run_tests:
        sys.exit(run_tests())
    else:
        sys.exit(main(args, paths))

# vim: set expandtab sw=4 ts=4: