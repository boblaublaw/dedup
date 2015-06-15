#!/bin/sh 

SUFFIX=ddmd5

function md5f() {
    if [ "x${1}" = x ]; then
        md5 
    else
        md5 "${1}" | cut -f2 -d\= | cut -c2-
    fi
}

function dir_depth() {
    dir=$1
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
    root=$1

    if [ ! -d "${root}" ]; then
        echo please supply a directory to hash
        exit 1
    fi

    echo hashing all files in ${root}...
    find "$root" -type f  | grep -v ".${SUFFIX}$" | while read f; do 
        hash="${f}.${SUFFIX}"
        if [ ! -f "${hash}" -o "${f}" -nt "${hash}" ]; then
            md5f "${f}" > "${hash}"
        fi
    done

    depth=`dir_depth "$root"`

    while [ $depth -gt 0 ]; do
        find "${root}" -type d -mindepth $depth -maxdepth $depth| grep -v '^.$' | grep -v '^..$' | while read subdir; do 
            echo checking subdir $subdir
            hash="${subdir}".${SUFFIX}
            if [ ! -f "${hash}" -o "${subdir}" -nt "${hash}" ]; then
                    cat "${subdir}"/*.${SUFFIX} 2> /dev/null | sort | md5f > "${hash}"
            fi
        done
        depth=$((depth - 1))
    done
    cat ${root}/*.ddmd5 2>/dev/null | sort | md5 > ${root}.${SUFFIX}
}

function clean_hashes() {
    root=$1

    if [ ! -d "${root}" ]; then
        echo please supply a directory to clean
        exit 1
    fi

    find "$root" -type f -name "*.${SUFFIX}" | while read f; do 
        rm "$f"
    done
    rm ${root}.${SUFFIX}
}

function usage() {
    cat << EOF
dedup.sh usage:

    dedup.sh <cmd> <cmdArgs>

where <cmd> is one of:
    hd      (hash directories):     hash all the files and directories in a directory
    cd      (clean directories):    remove all the hashfiles in a directory
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
    *)
        usage
        ;;
esac



