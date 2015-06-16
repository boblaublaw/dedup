#!/bin/sh 

SUFFIX=ddh
HASH=sha1
IGNORELIST=".DS_Store"

# this will need to be tuned to the hash function of choice:
function hashf() { 
    /bin/echo -n "$HASH:"
    if [ x"$1" = x ]; then
        openssl $HASH | cut -f2 -d\= | cut -c2-
    else
        openssl $HASH "${1}" | cut -f2 -d\= | cut -c2-
    fi
}

function dir_depth() {
    dir="$1"
    maxdep=1
    last=-1
    while [ 1 ]; do
        results=`find $dir -maxdepth $maxdep| wc -l`
        if [ $last -eq $results ]; then
            echo $((maxdep - 1))
            return
        fi
        last=$results
        maxdep=$((maxdep + 1))
    done
}

function hash_dir() {
    root="$1"

    if [ ! -d "${root}" ]; then
        echo please supply a directory to hash
        exit 1
    fi

    echo hashing all files in ${root}...
    find "$root" -type f  | grep -v ".${SUFFIX}$" | while read f; do 
        basefile=`basename "$f"`
        skip=0
        for ignore in $IGNORELIST; do
            if [ "$basefile" = "$ignore" ]; then   
                skip=1
                break
            fi
        done
        if [ $skip -eq 1 ]; then
            continue
        fi
        hash="${f}.${SUFFIX}"
        if [ ! -f "${hash}" -o "${f}" -nt "${hash}" ]; then
            hashf "${f}" > "${hash}"
        fi
    done

    depth=`dir_depth "$root"`

    while [ $depth -gt 0 ]; do
        find "${root}" -type d -mindepth $depth -maxdepth $depth| grep -v '^.$' | grep -v '^..$' | while read subdir; do 
            echo checking subdir $subdir
            hash="${subdir}".${SUFFIX}
            if [ ! -f "${hash}" -o "${subdir}" -nt "${hash}" ]; then
                    cat "${subdir}"/*.${SUFFIX} 2> /dev/null | sort | hashf > "${hash}"
            fi
        done
        depth=$((depth - 1))
    done
    cat ${root}/*.${SUFFIX} 2>/dev/null | sort | hashf > ${root}.${SUFFIX}
}

function clean_hashes() {
    root="$1"

    if [ ! -d "${root}" ]; then
        echo please supply a directory to clean
        exit 1
    fi

    find "$root" -type f -name "*.${SUFFIX}" | while read f; do 
        rm "$f"
    done
    rm -f ${root}.${SUFFIX}
}

function prescribe_cmds() {
    root="$1"

    find "$root" -name "*.${SUFFIX}" | while read hashfile; do 
        file=`basename "$hashfile" .${SUFFIX}`
        hash=`cat "$hashfile"`
        echo $file\|$hash
    done
}

function usage() {
    cat << EOF
dedup.sh usage:

    dedup.sh <cmd> <cmdArgs>

where <cmd> is one of:
    hd      (hash directories):     hash all the files and directories in a directory
    cd      (clean directories):    remove all the hashfiles in a directory
    pc      (prescribe commands):   generate a list of commands to resolve dups

EOF
}

case $1 in
    hd )
        shift
        echo hashing $@
        hash_dir $@
        ;;
    cd )
        shift
        echo cleaning $@
        clean_hashes $@
        ;;
    pc )
        shift
        echo prescribing commands for $@
        prescribe_cmds $@
        ;;
    *)
        usage
        ;;
esac



