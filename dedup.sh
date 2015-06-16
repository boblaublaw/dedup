#!/bin/sh 

SUFFIX=ddh
HASH=sha1
IGNORELIST=".DS_Store"

# this will need to be tuned to the hash function of choice:
function hashfunction() { 
    /bin/echo -n "${HASH}|"
    file="${1}"
    if [ x"${file}" = x ]; then
        openssl ${HASH} | cut -f2 -d\= | cut -c2-
    else
        openssl ${HASH} "${file}" | cut -f2 -d\= | cut -c2-
    fi
}

function dir_depth() {
    dir="${1}"
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

function create_dirhash() {
    subdir="${1}"
    hashfile="${subdir}.${SUFFIX}"
    #echo checking subdir $subdir with hashfile ${hashfile}
    if [ ! -f "${hashfile}" -o "${subdir}" -nt "${hashfile}" ]; then
        /bin/echo -n "d|" > "${hashfile}"
        cat "${subdir}"/*.${SUFFIX} 2> /dev/null | sort | hashfunction >> "${hashfile}"
    fi
}

function create_filehash() {
    file="${1}"
    hashfile="${file}.${SUFFIX}"
    if [ ! -f "${hashfile}" -o "${file}" -nt "${hashfile}" ]; then
        #/bin/echo -n "f|" > "${hashfile}"
        cat "${file}" | hashfunction >> "${hashfile}"
    fi
}

function hash_directory() {
    root="$1"

    if [ ! -d "${root}" ]; then
        echo please supply a directory to hash
        exit 1
    fi

    #echo hashing all files in ${root}...
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
        create_filehash "${f}"
    done

    return
    depth=`dir_depth "$root"`

    while [ $depth -gt 0 ]; do
        find "${root}" -type d -mindepth $depth -maxdepth $depth| grep -v '^.$' | grep -v '^..$' | while read subdir; do 
            create_dirhash "${subdir}"
        done
        depth=$((depth - 1))
    done
    create_dirhash "${root}"
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

function append() {

    while read l; do 
        echo $l; 
    done
    echo $@
}

function prescribe_cmds() {
    root="$1"

    find "$root" -name "*.${SUFFIX}" | while read hashfile; do 
        dir=`dirname "${hashfile}"`
        file=`basename "${hashfile}" .${SUFFIX}`
        hash=`cat "${hashfile}"`
        echo ${hash}\|${dir}/${file}
    done
    
    
}

function usage() {
    cat << EOF
dedup.sh usage:

    dedup.sh <dir> <cmd1> <cmd2> ... <cmdN>

where <cmd> is one of:
    hd      (hash directories):     hash all the files and directories in a directory
    cd      (clean directories):    remove all the hashfiles in a directory
    pc      (prescribe commands):   generate a list of commands to resolve dups

EOF
    exit 1
}


function process_cmd () {
    cmd=${1}
    dir="${2}"
    case $cmd in
        hd )
            shift
            #echo hashing ${dir}
            hash_directory "${dir}"
            ;;
        cd )
            shift
            #echo cleaning ${dir}
            clean_hashes "${dir}"
            ;;
        pc )
            shift
            #echo prescribing commands for ${dir}
            prescribe_cmds "${dir}"
            ;;
        *)
            usage
            ;;
    esac
}

if [ $# -lt 2 -o "${1}" = '-?' -o "${1}" = '-h' ]; then
    usage
fi
dir="${1}"
if [ ! -d "${dir}" ]; then
    echo ${dir} is not a directory.
    usage
fi
shift
cmds=$@
for cmd in ${cmds}; do
    process_cmd ${cmd} "${dir}" 
done

