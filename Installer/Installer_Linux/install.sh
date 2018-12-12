#!/bin/bash
#title          :install.sh
#description    :This script will install Golem and required dependencies
#author         :Golem Team
#email          :contact@golem.network
#date           :20170920
#version        :0.4
#usage          :sh install.sh
#notes          :Only for Ubuntu and Mint
#==============================================================================

# CONSTANTS
declare -r HOME=$(readlink -f ~)
declare -r CONFIG="$HOME/.local/.golem_version"
declare -r docker_script='docker_install.sh'
declare -r version_file='version'
declare -r hyperg_pack=/tmp/hyperg.tar.gz
declare -r PACKAGE="golem-linux.tar.gz"
declare -r ELECTRON_PACKAGE="electron.tar.gz"
declare -r GOLEM_DIR=$HOME'/golem'

# Questions
declare -i INSTALL_DOCKER=0
declare -i INSTALL_NVIDIA_DOCKER=0
declare -i INSTALL_NVIDIA_MODPROBE=0
declare -i reinstall=0

# PACKAGE VERSION
CURRENT_VERSION="0.1.0"
PACKAGE_VERSION="0.1.0"

# PARAMS
LOCAL_PACKAGE=""
UI_PACKAGE=""
declare -i DEPS_ONLY=0
declare -i DEVELOP=0

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
    # if want to install only deps,
    # we don't have to ask if want to install any dependency
    [[ ${DEPS_ONLY} -eq 1 ]] && return 1
    while [ 1 ]; do
        read -p "$@ " yn
        case ${yn} in
            y|Y ) return 1;;
            n|N ) return 0;;
            * ) warning_msg "Please answer yes or no.";;
        esac
    done
}

function release_url()
{
    json=$(wget -qO- --header='Accept: application/json' $1)
    echo ${json} | python3 -c '\
        import sys, json;                          \
        j = json.load(sys.stdin);                  \
        k = "browser_download_url";                \
        print([asset[k] for entry in j             \
                   if "assets" in entry            \
               for asset in entry["assets"]        \
                   if asset[k].find("linux") != -1 \
              ][0])'
}

# @brief check if dependencies (Docker, nvidia-docker + nvidia-modprobe)
# are installed and set proper 'global' variables
function check_dependencies()
{
    # Check if docker daemon exists
    if [[ -z "$( service --status-all 2>&1 | grep -F 'docker' )" ]]; then
        ask_user "Docker not found. Do you want to install it? (y/n)"
        INSTALL_DOCKER=$?
    else
        info_msg "Docker is already installed"
    fi

    # Check if nvidia-docker2 is installed
    if [[ -z "$(dpkg -s nvidia-docker2 | grep -i 'status: install ok installed')" ]]; then
        if [[ -z "$(lspci | grep -i nvidia)" ]]; then
            warning_msg "nvidia-docker is not supported: incompatible device"
        elif [[ ! -z "$(lsmod | grep -i nouveau)" ]]; then
            warning_msg "nvidia-docker is not supported: please install the proprietary driver"
        elif [[ -z "$(lsmod | grep -i nvidia)" ]]; then
            warning_msg "nvidia-docker is not supported: no compatible driver found"
        else
            ask_user "nvidia-docker not found. Do you want to install it? (y/n)"
            INSTALL_NVIDIA_DOCKER=$?
        fi
    else
        info_msg "nvidia-docker is already installed"
    fi

    # Check for nvidia-modprobe
    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then
        if [[ -z "$(which nvidia-modprobe)" ]]; then
            INSTALL_NVIDIA_MODPROBE=1
        else
            info_msg "nvidia-modprobe is already installed"
        fi
    fi
}


# @brief Install/Upgrade required dependencies
function install_dependencies()
{
    info_msg "INSTALLING GOLEM DEPENDENCIES"
    sudo id &> /dev/null
    if [[ $? -ne 0 ]]; then
        error_msg "Dependency installation requires sudo privileges"
        exit 1
    fi

    declare -a packages=( openssl pkg-config libjpeg-dev libopenexr-dev \
               libssl-dev autoconf libgmp-dev libtool libffi-dev \
               libgtk2.0-0 libxss1 libgconf-2-4 libnss3 libasound2 \
               libfreeimage3 )

    if [[ ${INSTALL_DOCKER} -eq 1 ]]; then
        info_msg "INSTALLING DOCKER"

        # Ubuntu 14.04 needs some additional dependencies
        if [[ $( lsb_release -r | awk '{print $2}' ) == '14.04' ]]; then
            packages+=("linux-image-extra-$(uname -r)" linux-image-extra-virtual)
        fi

        packages+=( apt-transport-https \
                    ca-certificates \
                    software-properties-common)
        wget -qO- https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
        sudo add-apt-repository \
            "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) \
            stable"
    fi

    docker_version="$(apt-cache madison docker-ce 2>/dev/null | head -1 | awk '{print $3}')"
    if [[ -z "${docker_version}" ]]; then
        packages+=(docker-ce)
    else
        packages+=(docker-ce=${docker_version})
    fi

    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then
        info_msg "INSTALLING NVIDIA-DOCKER"

        wget -qO- https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
        distribution=$(. /etc/os-release;echo ${ID}${VERSION_ID})

        wget -qO- https://nvidia.github.io/nvidia-docker/${distribution}/nvidia-docker.list | \
            sudo tee /etc/apt/sources.list.d/nvidia-docker.list

        packages+=(nvidia-docker2)
    fi

    if [[ ${INSTALL_NVIDIA_MODPROBE} -eq 1 ]]; then
        sudo apt-add-repository multiverse
        packages+=(nvidia-modprobe)
    fi

    declare -r hyperg=$(release_url "https://api.github.com/repos/golemfactory/golem-hyperdrive/releases")
    hyperg_release=$( echo ${hyperg} | cut -d '/' -f 8 | sed 's/v//' )
    # Older version of HyperG doesn't have `--version`, so need to kill
    ( hyperg_version=$( hyperg --version 2>/dev/null ) ) & pid=$!
    ( sleep 5s && kill -HUP ${pid} ) 2>/dev/null & watcher=$!
    if wait ${pid} 2>/dev/null; then
        pkill -HUP -P ${watcher}
        wait ${watcher}
    else
        hyperg_version=0.0.0
    fi
    if [[ ! -f $HOME/hyperg/hyperg ]] || [[ "$hyperg_release" > "$hyperg_version" ]]; then
        info_msg "Installing HyperG"
        wget --show-progress -qO- ${hyperg} > ${hyperg_pack}
        [[ -d $HOME/hyperg ]] && rm -rf $HOME/hyperg
        tar -xvf ${hyperg_pack} >/dev/null
        [[ "$PWD" != "$HOME" ]] && mv hyperg $HOME/
        [[ ! -f /usr/local/bin/hyperg ]] && sudo ln -s $HOME/hyperg/hyperg /usr/local/bin/hyperg
        [[ ! -f /usr/local/bin/hyperg-worker ]] && sudo ln -s $HOME/hyperg/hyperg-worker /usr/local/bin/hyperg-worker
        rm -f ${hyperg_pack} &>/dev/null
    fi
    sudo apt-get update >/dev/null
    echo -e "\e[91m"
    for package in ${packages[*]}; do
        sudo apt-get install -q -y ${package} >/dev/null
    done
    echo -e "\e[39m"
    if [[ ${INSTALL_DOCKER} -eq 1 ]]; then
        if [[ -z "${SUDO_USER}" ]]; then
            sudo usermod -aG docker ${USER}
        else
            sudo usermod -aG docker ${SUDO_USER}
        fi
        sudo docker run hello-world &>/dev/null
        if [[ ${?} -eq 0 ]]; then
            info_msg "Docker installed successfully"
        else
            warning_msg "Error occurred during installation"
            sleep 5s
        fi
    fi

    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then
        sudo pkill -SIGHUP dockerd
    fi
    info_msg "Done installing Golem dependencies"
}

# @brief Download latest Golem package (if package wasn't passed)
# @return 1 if error occurred, 0 otherwise
function download_package() {
    if [[ -f "$LOCAL_PACKAGE" ]]; then
        info_msg "Local package provided, skipping downloading..."
        cp "$LOCAL_PACKAGE" "/tmp/$PACKAGE"
    else
        info_msg "Downloading Golem package"
        if [[ ${DEVELOP} -eq 0 ]]; then
            golem_url=$(release_url "https://api.github.com/repos/golemfactory/golem/releases")
        else
            golem_url=$(release_url "https://api.github.com/repos/golemfactory/golem-dev/releases")
        fi
        wget --show-progress -qO- ${golem_url} > /tmp/${PACKAGE}
    fi
    if [[ ! -f /tmp/${PACKAGE} ]]; then
        error_msg "Cannot find Golem package"
        error_msg "Contact golem team: https://chat.golem.network/ or contact@golem.network"
        exit 1
    fi

    if [[ -f ${UI_PACKAGE} ]]; then
        info_msg "UI package provided, skipping downloading..."
        cp ${UI_PACKAGE} /tmp/${ELECTRON_PACKAGE}
    else
        info_msg "Downloading ui package (it may take awhile)"
        if [[ ${DEVELOP} -eq 0 ]]; then
            electron_url=$(release_url "https://api.github.com/repos/golemfactory/golem-electron/releases")
        else
            electron_url=$(release_url "https://api.github.com/repos/golemfactory/golem-electron-dev/releases")
        fi
        wget --show-progress -qO- ${electron_url} > /tmp/${ELECTRON_PACKAGE}
    fi
    if [[ ! -f /tmp/${ELECTRON_PACKAGE} ]]; then
        error_msg "Cannot find Electron package"
        error_msg "Contact golem team: https://chat.golem.network/ or contact@golem.network"
        exit 1
    fi
    return 0
}

# @brief Check if symlink is correct and if not, remove and create correct
# @param $1 Source file
# @param $2 Destination
# @return 0 on success, error code otherwise
function check_symlink()
{
    source=$1
    destination=$2
    point_to=$( ls -l ${destination} 2>/dev/null | rev | cut -d ' ' -f 1 | rev )
    [[ ${point_to} == ${source} ]] && return 0
    sudo rm -f ${destination} 2>/dev/null
    sudo ln -s ${source} ${destination}
    res=${?}
    if [[ -n "${SUDO_USER}" ]]; then
        sudo chown ${SUDO_USER}:${SUDO_USER} ${destination}
        sudo -H -u ${SUDO_USER} chmod 755 ${destination}
    fi
    return ${res}
}

# @brief Download and install golem
# @return 1 if error occurred, 0 otherwise
function install_golem()
{
    info_msg "Installing Golem"
    download_package
    result=$?
    if [[ ${result} -eq 1 ]]; then
        return 1
    fi

    tar -zxvf /tmp/${PACKAGE} >/dev/null
    if [[ ${?} -ne 0 ]]; then
        error_msg "ERROR) Cannot extract ${PACKAGE}. Exiting..."
        return 1
    fi
    PACKAGE_DIR=$( find . -maxdepth 1 -name "golem-*" -type d -print | head -n1 )
    if [[ ! -d ${PACKAGE_DIR} ]]; then
        error_msg "Error extracting package"
        return 1
    fi

    if [[ -f ${GOLEM_DIR}/golemapp ]]; then
        CURRENT_VERSION=$( ${GOLEM_DIR}/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
        PACKAGE_VERSION=$( ${PACKAGE_DIR}/golemapp -v 2>/dev/null  | cut -d ' ' -f 3 )
        NEWER_VERSION=$(printf "$CURRENT_VERSION\n$PACKAGE_VERSION" | sort -t '.' -k 1,1 -k 2,2 -k 3,3 -g | tail -n 1)
        if [[ "$CURRENT_VERSION" == "$PACKAGE_VERSION" ]]; then
            ask_user "Same version of Golem ($CURRENT_VERSION) detected. Do you want to reinstall Golem? (y/n)"
            [[ $? -eq 0 ]] && return 0
        elif [[ "$CURRENT_VERSION" == "$NEWER_VERSION" ]]; then
            ask_user "Newer version ($CURRENT_VERSION) of Golem detected. Downgrade to version $PACKAGE_VERSION? (y/n)"
            [[ $? -eq 0 ]] && return 0
        fi
    fi

    info_msg "Installing Golem into $GOLEM_DIR"
    [[ ! -d ${GOLEM_DIR} ]] && mkdir -p ${GOLEM_DIR}
    cp -rf ${PACKAGE_DIR}/* ${GOLEM_DIR}
    rm -rf ${PACKAGE_DIR} &>/dev/null

    tar -zxvf /tmp/${ELECTRON_PACKAGE} >/dev/null
    if [[ ${?} -ne 0 ]]; then
        error_msg "ERROR) Cannot extract ${ELECTRON_PACKAGE}. Exiting..."
        return 1
    fi
    ELECTRON_DIR=$(find . -maxdepth 1 -name "linux-unpacked" -type d -print | head -n1)
    if [[ ! -d ${ELECTRON_DIR} ]]; then
        error_msg "Error extracting package"
        return 1
    fi

    [[ ! -d ${GOLEM_DIR}/electron ]] && mkdir ${GOLEM_DIR}/electron
    cp -rf ${ELECTRON_DIR}/* ${GOLEM_DIR}/electron
    rm -rf ${ELECTRON_DIR} &>/dev/null
    rm -rf /tmp/${ELECTRON_PACKAGE} &>/dev/null
    rm -rf ${ELECTRON_DIR} &>/dev/null

    if [[ -n "${SUDO_USER}" ]]; then
        sudo chown -R ${SUDO_USER}:${SUDO_USER} ${GOLEM_DIR}
        sudo -H -u ${SUDO_USER} chmod -R 755 ${GOLEM_DIR}
    fi

    result=0
    check_symlink ${GOLEM_DIR}/electron/golem /usr/local/bin/golem
    result=$(( ${result} + $? ))
    check_symlink ${GOLEM_DIR}/golemapp /usr/local/bin/golemapp
    result=$(( ${result} + $? ))
    check_symlink ${GOLEM_DIR}/golemcli /usr/local/bin/golemcli
    result=$(( ${result} + $? ))
    [[ ${result} -eq 0 ]] && return 0 || return 1
}


# @brief Main function
function main()
{
    check_dependencies
    install_dependencies
    [[ ${DEPS_ONLY} -eq 1 ]] && return
    install_golem
    result=$?
    if [[ ${INSTALL_DOCKER} -eq 1 ]]; then
        info_msg "You need to restart your PC to finish installation"
    fi
    if [[ ${result} -ne 0 ]]; then
        error_msg "Installation failed"
    fi
    return ${result}
}

# @brief Print instruction
function help_message() {
    echo -e "\e[1mUsage: install.sh [<option> ...]\e[0m" >&2
    echo
    echo -e "\e[4mOptions:\e[0m"
    echo -e "   -g, --golem           package with Golem"
    echo -e "   -u, --ui              package with UI"
    echo -e "   -d, --deps-only       install only dependencies without Golem"
    echo -e "   -dev, --develop       install develop version"
    echo -e "   -h, --help            print this message"
    echo
}


while [[ $# -ge 1 ]]; do
    key="$1"
    case ${key} in
        -g|--golem)
        if [[ ! -f "$2" ]]; then
            help_message
            exit 1
        fi
        LOCAL_PACKAGE="$2"
        shift # past argument
        ;;
        -u|--uipackage)
        if [[ ! -f "$2" ]]; then
            help_message
            exit 1
        fi
        UI_PACKAGE="$2"
        shift # past argument
        ;;
        -dev|--develop)
        DEVELOP=1
        ;;
        -h|--help)
        help_message
        exit 0
        ;;
        -d|--deps-only)
        DEPS_ONLY=1
        ;;
        *) # unknown option
        error_msg "Unknown argument: $1"
        help_message
        exit 1
        ;;
    esac
    shift # past argument or value
done

main
exit $?
