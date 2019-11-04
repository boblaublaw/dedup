# dedup

[![Join the chat at https://gitter.im/boblaublaw/dedup](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/boblaublaw/dedup?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

### File and Directory Deduplication Tool ###

This project has two goals:
 * Improve disk utilization by reducing redundant copies of files on disk.  (If this is your only goal, consider a dedup filesystem like ZFS: https://blogs.oracle.com/bonwick/entry/zfs_dedup)
 * Make it easier to confidently delete entire directories and directory trees by consolidating deduplication analysis according to user preferences.

At this time of this writing, there are several tools similar to this one on github:
 * https://github.com/hgrecco/dedup
 * https://github.com/alessandro-gentilini/keep-the-best
 * https://github.com/jpillora/dedup
 * and no doubt more...

This project is similar to several of these projects in a few ways:
 * File comparisons are made by hashing their contents.
 * Caching hash results is supported.  Modification time is examined to update cache results when needed.
 * **THIS IS BETA SOFTWARE AND YOU ASSUME ALL RESPONSIBILITY FOR MISTAKES AND/OR LOST DATA**
 * Having gotten that out of the way, this script doesn't actually delete anything.  Instead a shell script is produced, intended for review before execution.

However, unlike these other projects, this project has a few additional features I found to be absent.  See the "Features" section below for details.

## Utilization

```
-h, --help            show this help message and exit
  -c, --clean-database  clean hash cache instead of normal operation
  -d DATABASE, --database DATABASE
                        name of DBM file to use for hash cache
  -e, --keep-empty-dirs
                        do not delete empty directories (default to false)
  -f, --keep-empty-files
                        do not delete empty files (default to false)
  -n, --nuke-database   delete the provided cache before starting
  -r, --reverse-selection
                        reverse the dir/file selection choices
  -s, --stagger-paths   always prefer files in argument order
  -t, --run-tests       run all the tests listed in 'test' subdir
  -v, --verbosity       increase output verbosity

Simplest Example:
     # Step one - generate a shell script named "remove_commands.sh"
     dedup.py some_path/ > remove_commands.sh

     # Step two - review the script to make sure everything is safe:
     less remove_commands.sh

     # Step Three - run the script:
     sh remove_commands.sh
```

## Features

### Comparing And Removing Redundant Directories

Comparing files for redundancy is comparatively trivial.  One could achieve deduplication by ignoring directories and removing empty directories afterwards.  However, this produces a larger number of output commands.  One recursive delete accomplishes the same goal with more readability.

Thus, in cases where ```some_dir``` would be empty after deduplication, this:
```
rm -rf some_dir
```
is preferred to this:
```
rm some_dir/file1
rm some_dir/file2
...
rm some_dir/fileN
rmdir some_dir
```
Likewise, if a tree of nested directories are all empty of files after deduplicaton, the whole tree would be removed. (This can be disabled with the `-e` option.)

### Winner Selection Strategy

In cases where files or directories are deemed redundant to one another, I choose the file or directory with the shallowest directory position to be the "keeper" (or selection "winner").  Other entries which are deeper in the directory structures are slated for removal.  In cases where the depth is equal, the shorter pathname is preferred.

For example, where all the following files contain the same data:
```
somedir/file1
somedir/file10
somedir/somedir2/file2
somedir3/somedir4/somedir5/file3
```
The first file would be selected to keep and the latter three would be marked for deletion.  

This strategy is effective in simplifying structures which have been copied into their own subdirectories.

### Advanced Winner Selection Strategy - Preferred Outcomes

By selecting the "stagger paths" mode (with the -s flag), dedup.py will automatically prefer the leftmost arguments supplied from the command line.

Example:
```
     dedup.py -s path1 path2 path3
```

All files in ```path1``` will be preferred to those in ```path2``` and ```path3```.  Likewise, All files in ```path2``` will be prefered to files in ```path3```.

### Really Advanced Winner Selection Strategy - Using Weighted Comparisons

If instead you want more control over weighting preferences, you can provide an optional *weighted score* to each directory or file at the time of invocation.

An ordinary run of dedup.py might look like this:
```
     dedup.py somedir somedir3
```
However, to prefer to keep files in ```somedir3```, even though it has a deeper subdirectory tree, you can add a weighted score to the ```somedir``` directory, making it less desirable for winner selection.
```
     dedup.py 10:somedir somedir3
```
Under the hood, this has the effect of adding 10 to the depth of every file and directory in ```somedir```.  It is advisable to use a weighted score that is GREATER than the maximum directory depth so that selection results are never mixed.  (This is exactly what the "-s/--stagger-path" option does to automatically calculate appropriate weights for you.)

Conversely, you can also add a "negative weight" to a directory you prefer:
```
     dedup.py somedir -10:somedir3
```

Just remember that elements closer to the "top" of input directory structures are what will be retained.  Even if the concept of a "negative" directory depth would suggest parent directories that do not actually exist, dedup.py will not actually attempt to navigate above the specified paths.

### Empty Files and Directories

Given how this tool compares files and directories, empty files (with 0 bytes) and empty subdirectories (with no children) confuse this algorithm.  Additionally, I assert empty directories clutter the resulting structure.  However, in some cases empty directories are files may be **REQUIRED** for the operation of certain software.  There are many instances where a program may count on simply the existence of a file to signify something meaningful, such as lock files.  *Be very careful to understand the purpose of every file or directory you delete.*

### Minimizing Output Commands

This tool will make several passes over the provided directory structures, analyzing for redundancy and empty files and directories until no more files or directories are marked for deletion.  

Once this analysis is complete, a minimal list of deletion commands is generated, resulting in fewer commands to review.  Often subsequent executions of dedup.py will be required, after moving, renaming, or deleting files manually.  (The -db flag is helpful for improving performance of subsequent runs.)

### Maximizing Trust and Minimizing Error

As mentioned in the directory comparison discussion, it is my goal to simplify the generated output script to maximize the ease of review and minimize the chance of error.  To this end I try to provide shell script comments before each delete command which offer an explanation as to why it is safe to delete the candidate file or directory.

If directories and files are marked for deletion in a given directory, such that the parent directory is deemed deletable, the parent directory delete command does not yet include rationalization for the deletion of all the children.  Please use --verbose mode if you want to see more explanation for each file and directory.
