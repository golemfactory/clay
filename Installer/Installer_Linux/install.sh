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
    if [ -n "$( pip -V 2>&1 | grep 'No command' )" ]; then
        INSTALL_PIP=1
    fi

    # Check if docker deamon exists
    if [ -n "$( service docker status | grep 'Loaded: not-found (Reason: No such file or directory)' )" ]; then
        ask_user "Docker not found. Do you want to install it? (y/n)"
        INSTALL_DOCKER=$?
    fi

    # check if geth is installed
    if [ -z "$( dpkg -l | grep geth )" ]; then
        ask_user "Geth not found. Do you want to install it? (y/n)"
        INSTALL_GETH=$?
    fi

    # check if ipfs is installed
    if [ -n "$( ipfs version 2>&1 | grep 'No command' )" ]; then
        ask_user "IPFS not found. Do you want to install it? (y/n)"
        INSTALL_IPFS=$?
    fi
}

# @brief Install required dependencies
function install_dependencies()
{
    # @todo can we do it without sudo? We can remove the last line and tell user to install it manually,
    # but still we need sudo when installing docker and geth, so until we find a better solution, it can be done in this way
    sudo apt-get update
    if [ $INSTALL_PIP -eq 1 ]; then
        sudo apt-get install python-pip
        pip install --upgrade pip
    fi
    if [ $INSTALL_DOCKER -eq 1 ]; then
        echo "INSTALLING DOCKER\n"
        checksum='63c26d22854e74d5736fab6e560d268b'
        script='docker_install.sh'
        # @todo any easy way? This will add PPA, update & install via apt
        wget -qO- http://get.docker.com > $script
        if [ "$( md5sum $script | awk '{print $1}' )" == "$checksum" ]; then
            sh $script
            sudo usermod -aG docker $(whoami)
        else
            error_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
        fi
        rm -f $script
    fi
    if [ $INSTALL_GETH -eq 1 ]; then
        echo "INSTALLING GET\n"
        # @todo any easy way? Without adding repository or building from source?
        sudo apt-get install software-properties-common
        sudo add-apt-repository -y ppa:ethereum/ethereum
        sudo apt-get update
        sudo apt-get install ethereum
    fi
    if [ $INSTALL_IPFS -eq 1 ]; then
        url='https://dist.ipfs.io/go-ipfs/v0.4.4/'
        package='go-ipfs_v0.4.4_linux-amd64.tar.gz'
        wget $url$package
        tar -zxvf $package
        rm -f $package
        mv go-ipfs/ipfs /usr/local/bin/ipfs
    fi
    sudo apt-get install openssl python-dev python-qt4 pyqt4-dev-tools libffi-dev pkg-config libjpeg-dev libopenexr-dev libssl-dev autoconf libgmp-dev libtool python-netifaces python-psutil build-essential
}

# @brief Download and install golem wheel
# @return 1 if error occured, 0 otherwise
function install_golem()
{
    package='golem-0.1.0-py2-none-any.whl'
    wget 'https://golem.network/'$package
    pip install $package
    if [ $? -eq 0 ]; then
        rm -f $package
        return 0
    else
        error_msg "Some error occured during installation"
        error_msg "Try to install it with 'sudo python -m pip install $package'"
        return 1
    fi
}

check_dependencies
install_dependencies
install_golem
[ $? -ne 0 ] && exit 1
if [ $INSTALL_DOCKER - eq 1 ]; then
    error_msg "You need to restart your computer to finish installation"
fi
exit 0
