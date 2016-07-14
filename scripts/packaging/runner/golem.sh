#!/usr/bin/env bash
SCRIPT=`basename "$0"`
# ----------------------------------------------------------------------------------------------------------------------

if [[ "${OSTYPE}" == "darwin"* ]]; then
    OS="darwin"
else
    OS="linux"
fi

IPFS_DIST_SRV="http://dist.ipfs.io"
IPFS_VER="v0.4.2"
IPFS_OS="${OS}-amd64"
IPFS_URL="${IPFS_DIST_SRV}/go-ipfs/${IPFS_VER}/go-ipfs_${IPFS_VER}_${IPFS_OS}.tar.gz"

UPDATE_SERVER="http://52.40.149.24:9999"
UPDATE_URL="${UPDATE_SERVER}/golem/"
UPDATE_FILE="${OS}.version"
UPDATE_PACKAGE="golem-linux-latest.zip"
UPDATE_FILE_URL="${UPDATE_URL}${UPDATE_FILE}"
UPDATE_PACKAGE_URL="${UPDATE_URL}${UPDATE_PACKAGE}"

LOCAL_VERSION_FILE=".version"
REMOTE_VERSION_FILE="remote.version"

EXEC_DIR=$(readlink -f $(find . -name "exe.*" -type d -print -quit))
UTILS_DIR="utils"
SCRIPTS_DIR="scripts"
EXEC_NAME="golemapp"
PATH=$IPFS_DIR:$EXEC_DIR:$PATH

# ----------------------------------------------------------------------------------------------------------------------

set -e

CWD="$(pwd)"
SCRIPT_DIR=$(readlink -f $(cd $(dirname "${BASH_SOURCE[0]}") && pwd))

cd "${SCRIPT_DIR}"

function download {
    URL=$1
    DIR=$2
    TAG=$3
    NAME=$(echo $URL | rev | cut -d/ -f1 | rev)

    EXT="${NAME##*.}"
    FILE="tmp.tar.${EXT}"

    echo "Downloading ${TAG}"
    wget --header="User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.87 Safari/537.36" \
        --header="dnt: 1" \
        --header="accept:*/*" \
        --header="accept-language:en-US,en;q=0.8" \
        --header="cache-control:max-age=0" \
        $URL \
        -O ${FILE}

    echo "Extracting ${TAG}"
    tar -xf "${FILE}"
    rm "${FILE}"
    mv -f *${TAG}* "${DIR}"
}

# ----------------------------------------------------------------------------------------------------------------------

function update {
    echo "Updating Golem"
    set -e

    UPDATE_DIR=".update"
    TAG="GOLEM"
    ZIP="golem-latest.zip"
    CWD=`pwd`

    rm -f "${ZIP}"
    rm -rf "${UPDATE_DIR}"
    wget "${UPDATE_PACKAGE_URL}" -O "${ZIP}"
    unzip -q "${ZIP}" -d ${UPDATE_DIR}
    rm -f "${ZIP}"

    if [ -d "${UPDATE_DIR}" ]; then
        # find . -maxdepth 1 ! -name "${UPDATE_DIR}" ! -name "." ! -name ".." -exec rm -rf {} +

        rm -rf "${EXEC_DIR}"
        rm -rf "${SCRIPTS_DIR}"
        rm -rf "${UTILS_DIR}"

        cp -a "${UPDATE_DIR}/golem/." "${CWD}"
        rm -rf "${UPDATE_DIR}"
    fi

    set +e

    # exec "./${SCRIPT}"
    echo "Golem updated"
    exit 0
}

function check_update {
    if [ -f $1 -a -f $2 ]; then
        LOCAL=$(head -n 1 $1)
        REMOTE=$(head -n 1 $2)
        if [ "${LOCAL}" != "" -a "${REMOTE}" != "" ]; then
            if [ ${REMOTE%.*} -eq ${LOCAL%.*} ] && [ ${REMOTE#*.} \> ${LOCAL#*.} ] || [ ${REMOTE%.*} -gt ${LOCAL%.*} ]; then
                update
            fi
        fi
    fi
}

set +e

if [ -f ".version" ]; then
    rm -f "${REMOTE_VERSION_FILE}"
    wget "${UPDATE_FILE_URL}" -O ${REMOTE_VERSION_FILE}
    check_update "${LOCAL_VERSION_FILE}" "${REMOTE_VERSION_FILE}"
    rm -f "${REMOTE_VERSION_FILE}"
else
    update
fi

set -e
# ----------------------------------------------------------------------------------------------------------------------

for img in "base" "blender" "luxrender"; do
    echo "Checking golem/${img}"
    STATUS=$(docker images -q "golem/${img}")

    if [[ "${STATUS}" == "" ]]; then
        echo "Building image golem/${img}"
        docker build -t golem/${img} -f scripts/Dockerfile.${img} .
    else
        echo "    image golem/${img} exists"
    fi
done

# ----------------------------------------------------------------------------------------------------------------------

IPFS_TAG="ipfs"
IPFS_DIR="${CWD}/${IPFS_TAG}"
IPFS_PATH="${CWD}/.ipfs"
IPFS_LOG="/tmp/ipfs-daemon.log"

# if [[ ! -d $IPFS_DIR ]]; then
#     download $IPFS_URL $IPFS_DIR $IPFS_TAG
# fi

set +e

# ----------------------------------------------------------------------------------------------------------------------

QT_PRESENT=$(ldconfig -v 2>/dev/null | grep QtCore.so.4)

if [[ ${QT_PRESENT} != "" ]]; then
    BACKUP_DIR="${SCRIPT_DIR}/.backup"
    mkdir -p "${BACKUP_DIR}"

    for FILENAME in "${EXEC_DIR}"/* ; do
        if [[ "${FILENAME}" == *"libQt"* ]]; then
            echo "Backing up and removing library ${FILENAME}"
            mv -f "${FILENAME}" "${BACKUP_DIR}"
        fi
    done
fi

# ----------------------------------------------------------------------------------------------------------------------

# killall ipfs > /dev/null 2>&1
# ipfs init > /dev/null 2>&1
# ipfs daemon > $IPFS_LOG &

# echo "Waiting for the IPFS daemon..."
# while ! grep 'Daemon is ready' "${IPFS_LOG}"; do sleep 1; done

now=$(date)
host=$(hostname)

if [[ $# -lt 1 ]]; then
    ARGS="--nogui"
else
    ARGS=$@
fi

"$EXEC_DIR/$EXEC_NAME" $ARGS >> "golem ${hostname} ${now}.log" 2>&1

# killall ipfs
cd "${CWD}"
