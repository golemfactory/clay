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


INSTALL_DOCKER=0
INSTALL_GETH=0
INSTALL_IPFS=0
INSTALL_PIP=0
declare -r CONFIG="$HOME/.local/.golem_version"
CURRENT_VERSION="0.1.0"
NEWEST_VERSION="0.1.0"
declare -r HOST="https://golem.network/"
PACKAGE="golem-0.1.0-py2-none-any.whl"


# @brief print error message
# @param error message
function error_msg()
{
    echo -e "\e[31m$@\e[39m" >&2
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
        * ) echo "Please answer yes or no.";;
    esac
}


# @brief check if dependencies (pip, Docker, IPFS and Ethereum) are installed and set proper 'global' variables
function check_dependencies()
{
    # check if pip is installed
    pip -v &>/dev/null
    if [ $? -ne 0 ]; then
        INSTALL_PIP=1
    fi

    # Check if docker deamon exists
    if [ -z "$( service --status-all | grep -F 'docker' )" ]; then
        ask_user "Docker not found. Do you want to install it? (y/n)"
        INSTALL_DOCKER=$?
    fi

    # check if geth is installed
    if [ -z "$( dpkg -l | grep geth )" ]; then
        ask_user "Geth not found. Do you want to install it? (y/n)"
        INSTALL_GETH=$?
    fi

    # check if ipfs is installed
    ipfs version &>/dev/null
    if [ $? -ne 0 ]; then
        ask_user "IPFS not found. Do you want to install it? (y/n)"
        INSTALL_IPFS=$?
    fi
}

# @brief Install required dependencies
function install_dependencies()
{
    to_install="openssl python-dev python-qt4 pyqt4-dev-tools libffi-dev pkg-config libjpeg-dev libopenexr-dev libssl-dev autoconf libgmp-dev libtool python-netifaces python-psutil build-essential"
    if [ $INSTALL_PIP -eq 1 ]; then
        to_install=$to_install" python-pip"
    fi
    if [ $INSTALL_DOCKER -eq 1 ]; then
        echo "INSTALLING DOCKER\n"
        checksum='63c26d22854e74d5736fab6e560d268b'
        script='docker_install.sh'
        # @todo any easy way? This will add PPA, update & install via apt
        wget -qO- http://get.docker.com > "/tmp/"$script
        if [ "$( md5sum /tmp/$script | awk '{print $1}' )" == "$checksum" ]; then
            sh "/tmp/"$script
            usermod -aG docker $(whoami)
        else
            error_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
        fi
        rm -f "/tmp/"$script
    fi
    if [ $INSTALL_GETH -eq 1 ]; then
        echo "INSTALLING GET\n"
        # @todo any easy way? Without adding repository or building from source?
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:ethereum/ethereum
        to_install=$to_install" ethereum"
    fi
    if [ $INSTALL_IPFS -eq 1 ]; then
        url='https://dist.ipfs.io/go-ipfs/v0.4.4/'
        package='go-ipfs_v0.4.4_linux-amd64.tar.gz'
        wget $url$package
        tar -zxvf $package
        rm -f $package
        mv go-ipfs/ipfs /usr/local/bin/ipfs
    fi
    apt-get update
    apt-get install -y $to_install
    pip install --upgrade pip
}


# @brief Read installed version and get newest version from server
function get_version()
{
    version=$( pip list 2>/dev/null | grep 'golem' | awk '{print $2}' | sed 's/[()]//g' )
    if [ -n "$version" ]; then
        CURRENT_VERSION=$version
    fi
    file="version"
    wget -q $HOST$file
    NEWEST_VERSION=$(cat $file )
    rm -f $file &>/dev/null
}


# @brief Download and install golem wheel
# @return 1 if error occured, 0 otherwise
function install_golem()
{
    wget $HOST$PACKAGE
    if [ -f $PACKAGE ]; then
        pip install $PACKAGE
        if [ $? -eq 0 ]; then
            rm -f $PACKAGE
            return 0
        else
            error_msg "Some error occurred during installation"
            error_msg "Contact Golem Team: http://golemproject.org:3000/ or contact@golem.network"
        fi
    else
        error_msg "Cannot download $PACKAGE"
        error_msg "Check you internet connection and contact Golem Team: http://golemproject.org:3000/ or contact@golem.network"
    fi
    return 1
}

# Make sure only root can run our script
if [[ $EUID -ne 0 ]]; then
   error_msg "This script must be run as root"
   exit 1
fi

get_version
if [ "$NEWEST_VERSION" > "$CURRENT_VERSION" ]; then
    PACKAGE="golem-"$NEWEST_VERSION"-py2-none-any.whl"
else
    echo "Newest version ($NEWEST_VERSION) is already installed"
    exit 0
fi

check_dependencies
install_dependencies
install_golem
[ $? -ne 0 ] && exit 1
echo "Successfully installed version $NEWEST_VERSION"
if [ $INSTALL_DOCKER -eq 1 ]; then
    error_msg "You need to restart your computer to finish installation"
fi
exit 0
