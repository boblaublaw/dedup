#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    This is the 'main()' for this package.
"""

import os
import sys
import time
import argparse
import shutil
from json import loads
from itertools import chain
from collections import defaultdict
from hashmap import HashMap
from hashdbobj import HashDbObj
from entrylist import EntryList


def sizeof_fmt(num, suffix='B'):
    """helper function to convert bytes to IEC values like '5.6MiB'."""
    prefix_list = ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']
    for unit in prefix_list:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def generate_delete(filename, outfile):
    """generates not-quite-safe rm commands.  TODO does not handle
    pathnames which contain both the ' and " characters.
    """
    # characters that we will wrap with double quotes:
    delim_test_chars = set("'()")
    if any((c in delim_test_chars) for c in filename):
        print('rm -rf "' + filename + '"', file=outfile)
    else:
        print("rm -rf '" + filename + "'", file=outfile)


def synthesize_report(results):
    """transforms a results object into a report structure"""
    winner_list = []
    all_marked_bytes = 0
    all_marked_count = 0
    for winner_name, loser_list in results.items():
        marked_count = len(loser_list)
        all_marked_count = all_marked_count + marked_count
        total_marked_bytes = 0
        if marked_count > 0:
            loser_list.sort(key=lambda x: x.pathname)
            for loser in loser_list:
                total_marked_bytes = total_marked_bytes + \
                    loser.count_bytes(True)
        all_marked_bytes = all_marked_bytes + total_marked_bytes
        new_result = {}
        new_result['winner_name'] = winner_name
        new_result['marked_count'] = marked_count
        new_result['total_marked_bytes'] = total_marked_bytes
        new_result['loser_list'] = loser_list
        winner_list.append(new_result)

    # set the order to present each result from this report:
    winner_list.sort(key=lambda x: x['total_marked_bytes'], reverse=True)
    return winner_list, all_marked_bytes, all_marked_count


def synthesize_reports(report_map):
    """transforms a results object into several report structures,
    each of which reflects a category of file or dir to be deleted"""
    report_list = []
    for report_name, report in report_map.items():
        new_report = {}
        new_report['report_name'] = report_name
        win = 'winner_list'
        total = 'total_marked_bytes'
        marked = 'marked_count'
        new_report[win], new_report[total], new_report[marked] = synthesize_report(
            report)
        report_list.append(new_report)

    report_list.sort(key=lambda x: x['total_marked_bytes'], reverse=True)
    return report_list


def generate_map_commands(report, empty_report_names, outfile):
    """transforms an analyzer report into a script that can be
    easily reviewed"""
    winner_list = report['winner_list']
    win_count = len(winner_list)
    # dont generate empty sections
    if win_count == 0:
        return
    report_name = report['report_name']
    total_marked_bytes = report['total_marked_bytes']
    marked_count = report['marked_count']

    print("\n" + '#' * 72, file=outfile)
    if report_name in empty_report_names:
        print('# ' + report_name + ': ' +
              str(marked_count) + ' to remove', file=outfile)
        print('# This section could make ' +
              sizeof_fmt(total_marked_bytes) + ' of file data redundant\n', file=outfile)
    else:
        print('# ' + report_name + ' : ' + str(win_count) +
              ' to keep and ' + str(marked_count) + ' to remove', file=outfile)
        print('# This section could make ' +
              sizeof_fmt(total_marked_bytes) + ' of file data redundant\n', file=outfile)

    for winner in winner_list:
        print("# This subsection could save " +
              sizeof_fmt(winner['total_marked_bytes']), file=outfile)
        if report_name not in empty_report_names:
            print("#      '" + winner['winner_name'] + "'", file=outfile)
        for loser in winner['loser_list']:
            generate_delete(loser.pathname, outfile)


def walklevel(some_dir, level=1):
    """helper function similar to os.walk but with a maxdepth param"""
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]


def run_test(args, parser, test_name):
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

    # pull arguments out of tests/${test_name}/opts.json
    try:
        test_args = loads(open(test_config_filename).read())
    except OSError:
        test_args = []

    # dedup tests/${test_name}/test
    args = parser.parse_args(test_args)
    results = analyze(args, [ephemeral_dir], scriptfile)
    generate_reports(results, scriptfile)
    scriptfile.close()
    os.system('sh ' + script_filename)
    # compare tests/${test_name}/test with tests/${test_name}/after
    test_result = os.system("diff --recursive --brief \"" +
                            ephemeral_dir + "\" \"" + after_dir + "\"")
    if test_result == 0:
        print('PASSED')
        return 0
    print('FAILED')
    return -1


def run_tests(args, parser):
    """
    walk all the dirs under 'tests' dir, treating each as a test case
    """
    for _, subdir_list, _ in walklevel('tests', 0):
        subdir_list.sort()
        for test_name in subdir_list:
            newpwd = 'tests' + os.path.sep + test_name + os.path.sep
            os.chdir(newpwd)
            if -1 == run_test(args, parser, test_name):
                return -1
            os.chdir('../..')

    # safe to ignore the following, just here to flex a helper function:
    ignore_this = sizeof_fmt(pow(1024, 8))
    ignore_this = sizeof_fmt(1024)
    return 0


def analyze(args, paths, outfile=sys.stdout):
    """
    analyze a list of paths for redundant files and directories.
    return a "results" object.
    """

    if len(paths) == 0 and args.stagger_paths:
        print('# -s/--stagger-paths specified, but no paths provided!')
        sys.exit(-1)

    if args.nuke_database:
        if args.verbosity > 0:
            print('# removing the database before we begin...' + args.database)
        try:
            os.remove(args.database)
        except OSError:
            pass  # ignore errors because its ok if this doesn't exist

    db = None
    if args.database is not None:
        db = HashDbObj(args, outfile)

    if len(paths) > 0:
        all_files = EntryList(paths, db, args)
        pass_count = 0
        # fake value to get the loop started:
        deleted = 1
        # while things are still being removed, keep working:
        while deleted > 0:
            sys.stdout.flush()
            h = HashMap(all_files, args, outfile)
            deleted_directories = all_files.prune_empty()

            h = HashMap(all_files, args, outfile)
            deleted_hash_matches = h.resolve()

            deleted = deleted_directories + deleted_hash_matches
            pass_count = pass_count + 1
            if deleted > 0:
                print('# ' + str(deleted) +
                      ' entries deleted on pass ' + str(pass_count), file=outfile)
        return all_files
    return None


def generate_reports(all_files, outfile=sys.stdout):
    """
    transforms an annotated structure describing all analyzed files and dirs
    into a set of report structures, each of which reflects a category of
    data to delete.
    """
    # a list of report names we will generate.  Note that these are later
    # indexed elsewhere, so be careful renaming
    regular_report_names = ['directories', 'files']
    empty_report_names = ['directories that are empty after reduction',
                          'directories that started empty', 'empty files']

    # create each category for files to delete in its own report.
    # reports are a dict indexed by "winner" that points to a metadata
    # and a list of losers
    report_maps = {}
    for report_name in chain(regular_report_names, empty_report_names):
        report_maps[report_name] = defaultdict(lambda: [])

    for _, e in all_files.contents.items():
        e.generate_reports(report_maps)

    report_lists = synthesize_reports(report_maps)

    for report in report_lists:
        generate_map_commands(report, empty_report_names, outfile)

    end_time = time.time()
    print('\n# total file data bytes marked for deletion ' +
          sizeof_fmt(all_files.count_bytes(deleted=True)), file=outfile)
    print('# total dedup running time: ' +
          str(end_time - start_time) + ' seconds.', file=outfile)


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
    parser.add_argument("-n", "--nuke-database", action="store_true",
                        help="delete the provided cache before starting")
    parser.add_argument("-r", "--reverse-selection", action="store_true",
                        help="reverse the dir/file selection choices")
    parser.add_argument("-s", "--stagger-paths", action="store_true",
                        help="always prefer files in argument order")
    parser.add_argument("-t", "--run-tests", action="store_true",
                        help="run all the tests listed in 'test' subdir")
    parser.add_argument("-v", "--verbosity", action="count", default=0,
                        help="increase output verbosity")
    args, paths = parser.parse_known_args()

    # requesting unit test execution discards all other options.
    if args.run_tests:
        sys.exit(run_tests(args, parser))
    else:
        res = analyze(args, paths)
        if res is not None:
            generate_reports(res)
        sys.exit(0)

# vim: set expandtab sw=4 ts=4:
