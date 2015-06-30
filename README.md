# dedup

At this time of this writing, there are several tools similar to this one on github:
 * https://github.com/hgrecco/dedup
 * https://github.com/alessandro-gentilini/keep-the-best
 * https://github.com/jpillora/dedup
 * and no doubt more...

This project is similar to several of these projects in a few ways:
 * File comparisons are made by hashing their contents.
 * This script doesn't actually delete anything.  Instead a shell script is produced, intended for review before execution.

However, unlike these other projects, this project has a few additional features I found to be absent.

## Utilization

```
dedup.py [ options ] path1 path2 path3 ... > commands.sh  # generate command list
vi commands.sh                                            # review command list
sh commands.sh                                            # execute commands

Where path can be any file or directory and where options can be:
 * -db/--database path_to_db_file       - cache hash results in a database for faster re-runs on large dirs
```

## Features

### Comparing And Removing Redundant Directories

Comparing files for redundancy is comparatively trivial.  One could achieve deduplication by ignoring directories and removing empty directories afterwards.  However, this produces a larger number of output commands where one recursive delete would accomplish the same goal.

Thus, this:
```
rm -rf some_dir
```
is preferred to this:
```
rm some_dir/file1
rm some_dir/file2
...
rm some_dir/fileN
```
in cases where no other files exist in ```some_dir```.

### Winner Selection Strategy

In cases where files or directories are deemed redundant to one another, I choose the file or directory with the shallowest directory position to be the "keeper" (or winner).  Other entries which are deeper in the directory structures are slated for removal.  In cases where the depth is equal, the shorter pathname is preferred.

For example, where all the following files contain the same data:
```
somedir/file1
somedir/file10
somedir/somedir2/file2
somedir3/somedir4/somedir5/file3
```
The first file would be selected to keep and the latter three would be marked for deletion.  

This strategy is effective in simplifying structures which have been copied into their own subdirectories.

I am entertaining the idea of adding support for creation time comparison, either in the base case, or as a tie-breaker.

### Empty Files and Directories

Given how this tool compares files and directories, empty files (with 0 bytes) and empty subdirectories (with no children) confuse this algorithm.  Additionally, I assert empty directories clutter the resulting structure.  However, in some cases empty directories are files may be **REQUIRED** for the operation of certain software.  There are many instances where a program may count on simply the existence of a file to signify something meaningful, such as lock files.  *Be very careful to understand the purpose of every file or directory you delete.*


### Minimizing Output Commands

This tool will make several passes over the provided directory structures, analyzing for redundancy and empty files and directories until no more files or directories are marked for deletion.  

Once this analysis is complete, a list of deletion commands is generated, resulting in fewer commands to review.

### Maximizing Trust and Minimizing Error

As mentioned in the directory comparison discussion, it is my goal to simplify the generated output script to maximize the ease of review and minimize the chance of error.  To this end I provide shell script comments before each delete command which offer an explanation as to why it is safe to delete the candidate file or directory.
