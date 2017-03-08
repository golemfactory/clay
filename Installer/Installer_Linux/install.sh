#!/bin/bash
#title          :install.sh
#description    :This script will install Golem and required dependencies
#author         :Golem Team
#email          :contact@golemnetwork.com
#date           :20170113
#version        :0.1
#usage          :sh install.sh
#notes          :Only for Ubuntu, Debian and Mint
#==============================================================================

# CONSTANTS
declare -r CONFIG="$HOME/.local/.golem_version"
declare -r HOST="https://golem.network/"
declare -r docker_checksum='63c26d22854e74d5736fab6e560d268b'
declare -r docker_script='docker_install.sh'
declare -r version_file='version'
declare -r ipfs_url='https://dist.ipfs.io/go-ipfs/v0.4.6/'
declare -r ipfs_package='go-ipfs_v0.4.6_linux-amd64.tar.gz'

# Questions
declare -i INSTALL_DOCKER=0
declare -i INSTALL_GETH=0
declare -i INSTALL_IPFS=0
declare -i reinstall=0

# PACKAGE VERSION
CURRENT_VERSION="0.1.0"
NEWEST_VERSION="0.1.0"
PACKAGE="golem-0.1.0-py2-none-any.whl"


# @brief print error message
# @param error message
function error_msg()
{
    echo -e "\n\n\e[91m$@\e[39m\n" >&2
}

# @brief print warning message
# @param warning message
function warning_msg()
{
    echo -e "\n\n\e[93m$@\e[39m\n"
}

# @brief print info message
# @param info message
function info_msg()
{
    echo -e "\n\n\e[92m$@\e[39m\n"
}

# @brief ask user
# @param question
# @return 1 if answer is 'yes', 0 if 'no'
function ask_user()
{
    read -p "$@ " yn
    case $yn in
        y|Y ) return 1;;
        n|N ) return 0;;
        * ) warning_msg "Please answer yes or no.";;
    esac
}

# @brief check if dependencies (pip, Docker, IPFS and Ethereum) are installed and set proper 'global' variables
function check_dependencies()
{
    # Check if docker deamon exists
    if [[ -z "$( service --status-all | grep -F 'docker' )" ]]; then
        ask_user "Docker not found. Do you want to install it? (y/n)"
        INSTALL_DOCKER=$?
    fi

    # check if geth is installed
    if [[ -z "$( dpkg -l | grep geth )" ]]; then
        ask_user "Geth not found. Do you want to install it? (y/n)"
        INSTALL_GETH=$?
    fi

    # check if ipfs is installed
    ipfs version &>/dev/null
    if [[ $? -ne 0 ]]; then
        ask_user "IPFS not found. Do you want to install it? (y/n)"
        INSTALL_IPFS=$?
    fi
}

# @brief Install required dependencies
function install_dependencies()
{
    info_msg "INSTALLING GOLEM DEPENDENCIES"
    apt-get update
    apt-get install -y openssl python-dev python-pyqt5 qt5-default pyqt5-dev-tools libffi-dev pkg-config libjpeg-dev libopenexr-dev libssl-dev autoconf libgmp-dev libtool python-netifaces python-psutil build-essential python-pip
    pip install --upgrade pip
    pip install service-identity zope.interface websocket-client openexr certifi devp2p cbor2 dill base58 multihash ovh weakreflist
    if [[ $INSTALL_GETH -eq 1 ]]; then
        info_msg "INSTALLING GETH"
        # @todo any easy way? Without adding repository or building from source?
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:ethereum/ethereum
        apt-get update
        apt-get install -y ethereum
    fi

    if [[ $INSTALL_IPFS -eq 1 ]]; then
        info_msg "INSTALLING IPFS"
        wget $ipfs_url$ipfs_package
        tar -zxvf $ipfs_package
        mv ./go-ipfs/ipfs /usr/local/bin/ipfs
        rm -f $ipfs_package
        rm -rf ./go-ipfs
    fi

    if [[ $INSTALL_DOCKER -eq 1 ]]; then
        info_msg "INSTALLING DOCKER"
        # @todo any easy way? This will add PPA, update & install via apt
        wget -qO- http://get.docker.com > /tmp/$docker_script
        if [[ "$( md5sum /tmp/$docker_script | awk '{print $1}' )" == "$docker_checksum" ]]; then
            bash /tmp/$docker_script
            usermod -aG docker $SUDO_USER
        else
            warning_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
            sleep 5s
        fi
        rm -f /tmp/$docker_script
    fi
}

function get_golem_version()
{
    info_msg "Checking Golem version"
    installed_version=$( pip list 2>/dev/null | grep 'golem' | awk '{print $2}' | sed 's/[()]//g' )
    newest_version=$(wget -O- -q $HOST$version_file)
    PACKAGE="golem-$newest_version-py2-none-any.whl"
    if [[ ! "$newest_version" > "$installed_version" ]]; then     # @todo need to be upgraded in versioning
        ask_user "Newest version ($newest_version) is already installed. Do you want to reinstall? (y/n)"
        reinstall=$?
        [[ $reinstall -eq 0 ]] && return 1
    fi
    return 0
}

# @brief Download and install golem wheel
# @return 1 if error occurred, 0 otherwise
function install_golem()
{
    wget $HOST$PACKAGE
    if [[ -f $PACKAGE ]]; then
        if [[ $reinstall -eq 0 ]]; then
            pip install $PACKAGE
            result=$?
        else
            pip install --upgrade --force-reinstall $PACKAGE
            result=$?
        fi
        if [[ $result -eq 0 ]]; then
            rm -f $PACKAGE
            return 0
        else
            error_msg "Some error occurred during installation"
            error_msg "Contact Golem Team: http://golemproject.org:3000/ or contact@golem.network"
        fi
        rm -f $PACKAGE
    else
        error_msg "Cannot download $PACKAGE"
        error_msg "Check you internet connection and contact Golem Team: http://golemproject.org:3000/ or contact@golem.network"
    fi
    return 1
}

# @brief Main function
function main()
{
    # Make sure only root can run our script
    if [[ $EUID -ne 0 ]]; then
        ask_user "This script need sudo access. Do you wan to continue? (y/n)"
        [[ $? -eq 1 ]] && exec sudo bash "$0" || return 1
    fi
    check_dependencies
    install_dependencies
    get_golem_version
    [[ $? -ne 0 ]] && return 0
    install_golem
    [[ $? -ne 0 ]] && return 1 || return 0
}

main
result=$?
if [[ $result -eq 0 ]]; then
    info_msg "You need to restart your PC to finish installation"
    exit 0
else
    error_msg "Installation failed"
    exit 1
fi