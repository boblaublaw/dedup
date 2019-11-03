#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    This is the 'main()' for this package.
"""
import os
import sys
import time
import shutil
import argparse
from json import loads
from hashmap import HashMap
from dirlist import DirList
from hashdbobj import HashDbObj
from report import generate_reports


def run_test(args, parser, test_name, start_time):
    """
    executes a single test via several steps:
        1. remove cruft from previous executions.
        2. duplicate a "before" dir into a temporary dir called "ephemeral".
        3. analyze "ephemeral" and produce "ephemeral.sh".
        4. run "ephemeral.sh" (which deletes files from "ephemeral").
        5. compare "ephemeral" dir to the "after" dir, expecting no difference.
    """
    print('Running test ' + test_name + ': ', end="")
    ephemeral_dir = 'ephemeral'
    before_dir = 'before'
    after_dir = 'after'
    test_config_filename = 'opts.json'
    script_filename = 'ephemeral.sh'
    scriptfile = open(script_filename, "w+")

    # unconditonally remove the ephemeral_dir
    shutil.rmtree(ephemeral_dir, ignore_errors=True)

    # create the ephemeral_dir based on the before_dir
    shutil.copytree(before_dir, ephemeral_dir, symlinks=False, ignore=None)

    # pull arguments out of tests/${test_name}/opts.json, if they exist
    test_args = []
    expected_pass = 0
    test_paths = [ ephemeral_dir ]
    twice = False
    runs = 1

    try:
        opts = loads(open(test_config_filename).read())
    except OSError:
        opts = {}

    if "args" in opts:
        test_args = opts["args"]
    if "paths" in opts:
        test_paths = opts["paths"]
    if "twice" in opts and opts["twice"]:
        runs = 2
    if "expected_pass" in opts:
        expected_pass = opts["expected_pass"]

    # prepare arguments
    args = parser.parse_args(test_args)

    # run as many times as requested:
    for i in range(1,runs+1):
        print("# run number " + str(i), file=scriptfile)
        results = analyze(args, test_paths, scriptfile)
        if results is None:
            if expected_pass:
                print("FAILED (failed analyze")
                return -1
            else:
                print("PASSED")
                return 0

    generate_reports(results, scriptfile, start_time)
    scriptfile.close()
    # run the generated script to delete from the ephemeral dir
    exec_result = os.system('sh ' + script_filename)
    if exec_result != 0:
        print('FAILED (script fail')
        return -1

    # compare tests/${test_name}/test with tests/${test_name}/after
    test_result = os.system("diff --recursive --brief \"" +
                            ephemeral_dir + "\" \"" + after_dir + "\"")
    if test_result == 0:
        print('PASSED')
        return 0
    print('FAILED (unexpected results)')
    return -1


def run_tests(args, parser, start_time):
    """
    run all the requested test cases, each described as a dir under "tests"
    """
    g = os.walk('tests')
    _, test_list, _ = next(g)

    # filter to just the requested test(s)
    # this will be '00' if all tests are requested.
    requested_test = ( '%02d' % int(args.run_tests))
    if requested_test != '00':
        test_list = [x for x in test_list if x[:2] == requested_test]
    else:
        test_list.sort()

    # run the requested test(s):
    for test_name in test_list:
        if test_name[:2] == requested_test or requested_test == '00':
            newpwd = 'tests' + os.path.sep + test_name + os.path.sep
            os.chdir(newpwd)
            if -1 == run_test(args, parser, test_name, start_time):
                return -1
            os.chdir('../..')
    return 0


def analyze(args, paths, outfile=sys.stdout):
    """
    analyze a list of paths for redundant files and directories.
    return a "results" object.

    returns None on failure
    """
    if len(paths) == 0 and args.stagger_paths:
        print('# -s/--stagger-paths specified, but no paths provided!', file=outfile)
        return None

    db = None
    if args.database is not None:
        db = HashDbObj(args, outfile)

    if len(paths) > 0:
        all_files = DirList(paths, db, args)

        hm = HashMap(all_files, args, outfile)

        # find and mark redundant files for deletion
        deleted = hm.resolve()
        # find and mark redundant empty directories for deletion
        deleted = deleted + all_files.prune_empty()

        print('# ' + str(deleted) + ' entries marked for deletion',
              file=outfile)

        if db is not None:
            db.close()
        return all_files
    return None


if __name__ == '__main__':
    start_time = time.time()
    desc = "generate commands to eliminate redundant files and directories"
    afterword = """
Simplest Example:
 # Step one - generate a shell script named "remove_commands.sh"
 dedup.py some_path/ > remove_commands.sh

 # Step two - review the script to make sure everything is safe:
 less remove_commands.sh

 # Step Three - run the script:
 sh remove_commands.sh
"""
    parser = argparse.ArgumentParser(description=desc,
                                     epilog=afterword,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-d", "--database",
                        help="name of DBM file to use for hash cache")
    parser.add_argument("-e", "--keep-empty-dirs", action="store_true",
                        help="do not delete empty directories (default to false)")
    parser.add_argument("-f", "--keep-empty-files", action="store_true",
                        help="do not delete empty files (default to false)")
    parser.add_argument("-r", "--reverse-selection", action="store_true",
                        help="reverse the dir/file selection choices")
    parser.add_argument("-s", "--stagger-paths", action="store_true",
                        help="always prefer files in argument order")
    parser.add_argument("-t", "--run-tests", nargs='?', const=0, default=-1, type=int,
                        help="run all the tests listed in 'test' subdir")
    parser.add_argument('--foo', )
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                        help="increase output verbosity")
    args, paths = parser.parse_known_args()

    # if args.run_tests is -1, we do not run tests
    if args.run_tests == -1:
        res = analyze(args, paths)
        if res is None:
            sys.exit(-1)
        else:
            generate_reports(res, sys.stdout, start_time)
    else:
        sys.exit(run_tests(args, parser, start_time))

# vim: set expandtab sw=4 ts=4:
