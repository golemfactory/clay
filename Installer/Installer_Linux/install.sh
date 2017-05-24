#!/bin/bash
#title          :install.sh
#description    :This script will install Golem and required dependencies
#author         :Golem Team
#email          :contact@golemnetwork.com
#date           :20170418
#version        :0.2
#usage          :sh install.sh
#notes          :Only for Ubuntu and Mint
#==============================================================================

function release_url()
{
    json=$(wget -qO- --header='Accept: application/json' $1)
    echo ${json} | python -c '\
        import sys, json;                          \
        j = json.load(sys.stdin);                  \
        k = "browser_download_url";                \
        print([asset[k] for entry in j             \
                   if "assets" in entry            \
               for asset in entry["assets"]        \
                   if asset[k].find("linux") != -1 \
              ][0])'
}

# CONSTANTS
declare -r HOME=$(readlink -f ~)
declare -r CONFIG="$HOME/.local/.golem_version"
declare -r golem_package=$(release_url "https://api.github.com/repos/golemfactory/golem/releases")
declare -r docker_checksum='1f4ffc2c1884b3e499de90f614ac05a7'
declare -r docker_script='docker_install.sh'
declare -r version_file='version'
declare -r hyperg=$(release_url "https://api.github.com/repos/mfranciszkiewicz/golem-hyperdrive/releases")

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
    if [[ -z "$( dpkg -l | awk '{print $2}' | grep geth )" ]]; then
        ask_user "Geth not found. Do you want to install it? (y/n)"
        INSTALL_GETH=$?
    fi
}

# @brief Install required dependencies
function install_dependencies()
{
    info_msg "INSTALLING GOLEM DEPENDENCIES"
    sudo id > /dev/null
    if [[ $? -ne 0 ]]; then
        error_msg "Dependency installation requires sudo privileges"
        exit 1
    fi

    sudo apt-get update
    sudo apt-get install -y openssl pkg-config libjpeg-dev libopenexr-dev libssl-dev autoconf libgmp-dev libtool qt5-default libffi-dev
    if [[ $INSTALL_GETH -eq 1 ]]; then
        info_msg "INSTALLING GETH"
        # @todo any easy way? Without adding repository or building from source?
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository -y ppa:ethereum/ethereum
        sudo apt-get update
        sudo apt-get install -y ethereum
    fi

    if [[ $INSTALL_DOCKER -eq 1 ]]; then
        info_msg "INSTALLING DOCKER"
        # @todo any easy way? This will add PPA, update & install via apt
        wget -qO- https://get.docker.com > /tmp/$docker_script
        if [[ "$( md5sum /tmp/$docker_script | awk '{print $1}' )" == "$docker_checksum" ]]; then
            bash /tmp/$docker_script
            if [[ $? -ne 0 ]]; then
                warning_msg "Cannot install docker. Install it manually: https://docs.docker.com/engine/installation/"
                sleep 5s
            fi
            if [[ $UID -ne 0 ]]; then
                sudo usermod -aG docker ${USER}
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
        [[ ! -f /usr/local/bin/hyperg ]] && sudo ln -s $HOME/hyperg/hyperg /usr/local/bin/hyperg
        rm -f /tmp/hyperg.tar.bz2 &>/dev/null
    fi
    info_msg "Done installing Golem dependencies"
}

function download_package() {
    if [[ -f "$LOCALPACKAGE" ]]; then
        info_msg "Local package provided, skipping downloading..."
        cp "$LOCALPACKAGE" "/tmp/$PACKAGE"
    else
        info_msg "Downloading package from $golem_package"
        wget -qO- "$golem_package" > /tmp/$PACKAGE
    fi
    if [[ ! -f /tmp/$PACKAGE ]]; then
        error_msg "Error unpacking package"
        error_msg "Contact golem team: http://golemproject.org:3000/ or contact@golem.network"
        exit 1
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
    PACKAGE_DIR=$(find . -maxdepth 1 -name "golem-*" -type d -print | head -n1)
    if [[ ! -d $PACKAGE_DIR ]]; then
        error_msg "Error extracting package"
        return 1
    fi

    if [[ -f $GOLEM_DIR/golemapp ]]; then
        CURRENT_VERSION=$( ${GOLEM_DIR}/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
        PACKAGE_VERSION=$( ${PACKAGE_DIR}/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
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
    [[ ! -d $GOLEM_DIR ]] && mkdir -p $GOLEM_DIR
    cp -R ${PACKAGE_DIR}/* ${GOLEM_DIR}
    rm -f /tmp/${PACKAGE} &>/dev/null
    rm -rf ${PACKAGE_DIR} &>/dev/null
    [[ ! -f /usr/local/bin/golemapp ]] && sudo ln -s $GOLEM_DIR/golemapp /usr/local/bin/golemapp
    [[ ! -f /usr/local/bin/golemcli ]] && sudo ln -s $GOLEM_DIR/golemcli /usr/local/bin/golemcli
    return 0
}


# @brief Main function
function main()
{
    check_dependencies
    install_dependencies
    install_golem
    result=$?
    if [[ $INSTALL_DOCKER -eq 1 ]]; then
        info_msg "You need to restart your PC to finish installation"
    fi
    if [[ $result -ne 0 ]]; then
        error_msg "Installation failed"
    fi
    return $result
}

main
exit $?
