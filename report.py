# -*- coding: utf-8 -*-

"""
   all the output scripts are generated here

   this whole thing should be refactored for OOP
"""
import sys
import time
from itertools import chain
from collections import defaultdict


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
              sizeof_fmt(total_marked_bytes) + ' of file data redundant', file=outfile)
    else:
        print('# ' + report_name + ' : ' + str(win_count) +
              ' to keep and ' + str(marked_count) + ' to remove', file=outfile)
        print('# This section could make ' +
              sizeof_fmt(total_marked_bytes) + ' of file data redundant', file=outfile)

    for winner in winner_list:
        print("\n# This subsection could save " +
              sizeof_fmt(winner['total_marked_bytes']), file=outfile)
        if report_name not in empty_report_names:
            print("#      '" + winner['winner_name'] + "'", file=outfile)
        for loser in winner['loser_list']:
            generate_delete(loser.pathname, outfile)


def generate_reports(all_files, outfile, start_time):
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

    # safe to ignore the following, just here to flex a helper function:
    ignore_this = sizeof_fmt(pow(1024, 8))
    ignore_this = sizeof_fmt(1024)

# vim: set expandtab sw=4 ts=4:
