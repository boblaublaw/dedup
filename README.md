# dedup

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
dedup.py [ options ] [weight:]path1 [weight:]path2 [...] > commands.sh  # generate command list
vi commands.sh                                                          # review command list
sh commands.sh                                                          # execute commands

Where path can be any file or directory with an optional weight prefix.

Where options can be:
 * -v/--verbose                         - show some rationale
 * -s/--stagger-paths                   - prefer input arguments from left to 
                                          right.  (automatically weight each
                                          argument to prevent overlap.)
 * -db/--database path_to_db_file       - cache hash results in a database for 
                                          faster re-runs on large dirs. (When
                                          specifying a pathname, do not supply
                                          the .db extension.  anydbm adds this
                                          on its own.)
 * -cdb/--clean-database                - install of calculating digests and
                                          eliminating duplicates, dedup will
                                          check every file in the provided db
                                          to check if it exists.  if it does not
                                          exist in the filesystem, it is removed
                                          from the db.

Simplest Example:
     dedup.py path1 path2

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
in cases where ```some_dir``` would be left empty after deduplication.

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

### Advanced Winner Selection Strategy - Using Weighted Comparisons

If instead you prefer that ```somedir3/somedir4/somedir5/file3``` be selected as the keeper of the candidate examples above, you can provide an optional *weighted score* to each directory or file at the time of invocation.

An ordinary run of dedup.py might look like this:
```
     dedup.py somedir somedir3
```
However, to prefer to keep files in ```somedir3```, even though it has a deeper subdirectory tree, you can add a weighted score to the ```somedir``` directory, making it less desirable for winner selection.
```
     dedup.py 10:somedir somedir3
```
Under the hood, this has the effect of adding 10 to the depth of every file and directory in ```somedir```.  It is advisable to use a weighted score that is GREATER than the maximum directory depth so that selection results are never mixed.  (Refer to the "--stagger-path" option to see how dedup.py can automatically calculate depths for you.)

Conversely, you can also add a "negative weight" to a directory you prefer:
```
     dedup.py somedir -10:somedir3
```

Just remember that elements closer to the "top" of input directory structures are what will be retained.  Even if the concept of a "negative" directory depth would suggest parent directories that do not actually exist, dedup.py will not actually attempt to navigate above the specified paths.

### Advanced Winner Selection Strategy - Automatic Weight Calculations

By selecting the "stagger paths" mode (with the -s flag), dedup.py will automatically calculate appropriate weights for each input argument based on their maximum directory depth such that leftmost arguments are preferred in the case of all file and directory collisions.

Example:
```
     dedup.py -s path1 path2 path3
```

All files in ```path1``` will be preferred to those in ```path2``` and ```path3```.  Likewise, All files in ```path2``` will be prefered to files in ```path3```.

### Empty Files and Directories

Given how this tool compares files and directories, empty files (with 0 bytes) and empty subdirectories (with no children) confuse this algorithm.  Additionally, I assert empty directories clutter the resulting structure.  However, in some cases empty directories are files may be **REQUIRED** for the operation of certain software.  There are many instances where a program may count on simply the existence of a file to signify something meaningful, such as lock files.  *Be very careful to understand the purpose of every file or directory you delete.*


### Minimizing Output Commands

This tool will make several passes over the provided directory structures, analyzing for redundancy and empty files and directories until no more files or directories are marked for deletion.  

Once this analysis is complete, a list of deletion commands is generated, resulting in fewer commands to review.

### Maximizing Trust and Minimizing Error

As mentioned in the directory comparison discussion, it is my goal to simplify the generated output script to maximize the ease of review and minimize the chance of error.  To this end I provide shell script comments before each delete command which offer an explanation as to why it is safe to delete the candidate file or directory.
  
