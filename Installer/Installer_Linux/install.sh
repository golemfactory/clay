#!/bin/bash
#title          :install.sh
#description    :This script will install Golem and required dependencies
#author         :Golem Team
#email          :contact@golemnetwork.com
#date           :20170113
#version        :0.1
#usage          :sh install.sh
#notes          :Only for Ubuntu and Mint
#==============================================================================

# CONSTANTS
declare -r CONFIG="$HOME/.local/.golem_version"
declare -r HOST="https://golem.network/"
declare -r docker_checksum='82e964b9a14d294268e4571f542b1508'
declare -r docker_script='docker_install.sh'
declare -r version_file='version'
declare -r hyperg='https://github.com/mfranciszkiewicz/golem-hyperdrive/releases/download/v0.1.2/hyperg_0.1.2_linux-amd64.tar.bz2'
declare -r HOME='/home/'$SUDO_USER

# Questions
declare -i INSTALL_DOCKER=0
declare -i INSTALL_GETH=0
# declare -i INSTALL_IPFS=0 # to restore IPFS revert this commit
declare -i reinstall=0

# PACKAGE VERSION
CURRENT_VERSION="0.1.0"
PACKAGE_VERSION="0.1.0"
PACKAGE="golem-linux.tar.gz"
GOLEM_DIR=$HOME'/golem/'

# PARAMS
LOCALPACKAGE=$1

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
    while [ 1 ]; do
        read -p "$@ " yn
        case $yn in
            y|Y ) return 1;;
            n|N ) return 0;;
            * ) warning_msg "Please answer yes or no.";;
        esac
    done
}

# @brief check if dependencies (pip, Docker, and Ethereum) are installed and set proper 'global' variables
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
}

# @brief Install required dependencies
function install_dependencies()
{
    info_msg "INSTALLING GOLEM DEPENDENCIES"
    apt-get update
    apt-get install -y openssl pkg-config libjpeg-dev libopenexr-dev libssl-dev autoconf libgmp-dev libtool qt5-default libffi-dev
    if [[ $INSTALL_GETH -eq 1 ]]; then
        info_msg "INSTALLING GETH"
        # @todo any easy way? Without adding repository or building from source?
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:ethereum/ethereum
        apt-get update
        apt-get install -y ethereum
    fi

    if [[ $INSTALL_DOCKER -eq 1 ]]; then
        info_msg "INSTALLING DOCKER"
        # @todo any easy way? This will add PPA, update & install via apt
        wget -qO- http://get.docker.com > /tmp/$docker_script
        if [[ "$( md5sum /tmp/$docker_script | awk '{print $1}' )" == "$docker_checksum" ]]; then
            bash /tmp/$docker_script
            if [[ $? -ne 0 ]]; then
                warning_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
                sleep 5s
            fi
        else
            warning_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
            sleep 5s
        fi
        rm -f /tmp/$docker_script
    fi

    if [[ ! -f $HOME/hyperg/hyperg ]]; then
        info_msg "Installing HyperG"
        wget -qO- $hyperg > /tmp/hyperg.tar.bz2
        tar -vxjf /tmp/hyperg.tar.bz2
        mv hyperg $HOME/
        [[ ! -f /usr/local/bin/hyperg ]] && ln -s $HOME/hyperg/hyperg /usr/local/bin/hyperg
        rm -f /tmp/hyperg.tar.bz2 &>/dev/null
    fi
    info_msg "Done installing Golem dependencies"
}

function download_package() {
    if [[ -f "$LOCALPACKAGE" ]]; then
        info_msg "Local package provided, skipping downloading..."
        cp "$LOCALPACKAGE" "/tmp/$PACKAGE"
    else
        info_msg "Downloading package from $HOST$PACKAGE"
        wget -qO- "$HOST$PACKAGE" > /tmp/$PACKAGE
    fi
    if [[ ! -f /tmp/$PACKAGE ]]; then
        error_msg "Error unpacking package"
        error_msg "Contact golem team: http://golemproject.org:3000/ or contact@golem.network"
        return 1
    fi
}

# @brief Download and install golem
# @return 1 if error occurred, 0 otherwise
function install_golem()
{
    download_package
    result=$?
    if [[ $result -eq 1 ]]; then
        return 1
    fi
    tar -zxvf /tmp/$PACKAGE
    if [[ -f $GOLEM_DIR/golemapp ]]; then
        CURRENT_VERSION=$( $GOLEM_DIR/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
        PACKAGE_VERSION=$( dist/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
        if [[ "$CURRENT_VERSION" == "$PACKAGE_VERSION" ]]; then
            ask_user "Same version of Golem ($CURRENT_VERSION) detected. Do you want to reinstall Golem? (y/n)"
            [[ $? -eq 0 ]] && return 0
        fi
        if [[ "$CURRENT_VERSION" > "$PACKAGE_VERSION" ]]; then
            ask_user "Newer version ($CURRENT_VERSION) of Golem detected. Downgrade to version $PACKAGE_VERSION? (y/n)"
            [[ $? -eq 0 ]] && return 0
        fi
    fi
    info_msg "Installing Golem into $GOLEM_DIR"
    [[ ! -d $GOLEM_DIR ]] && sudo -u $SUDO_USER mkdir -p $GOLEM_DIR
    mv dist/* $GOLEM_DIR
    rm -f /tmp/$PACKAGE &>/dev/null
    rm -rf dist &>/dev/null
    [[ ! -f /usr/local/bin/golemapp ]] && ln -s $GOLEM_DIR/golemapp /usr/local/bin/golemapp
    [[ ! -f /usr/local/bin/golemcli ]] && ln -s $GOLEM_DIR/golemcli /usr/local/bin/golemcli
    return 0
}


# @brief Main function
function main()
{
    # Make sure only root can run our script
    if [[ $EUID -ne 0 ]]; then
        ask_user "This script need sudo access. Do you want to continue? (y/n)"
        [[ $? -eq 1 ]] && exec sudo bash "$0" || return 1
    fi
    check_dependencies
    install_dependencies
    install_golem
    result=$?
    if [[ $INSTALL_DOCKER -eq 1 ]]; then
        info_msg "You need to restart your PC to finish installation"
    fi
    if [[ $result -eq 1 ]]; then
        error_msg "Installation failed"
    fi
    return $result
}

main
exit $?
