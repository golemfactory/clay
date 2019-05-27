#!/bin/bash
#title          :install.sh
#description    :This script will install Golem and required dependencies
#author         :Golem Team
#email          :contact@golem.network
#date           :20190111
#version        :0.5
#usage          :sh install.sh
#notes          :Only for Ubuntu and Mint
#==============================================================================

# CONSTANTS
declare -r PYTHON=python3
declare -r HOME=$(readlink -f ~)
declare -r GOLEM_DIR="$HOME/golem"
declare -r PACKAGE="golem-linux.tar.gz"
declare -r HYPERG_PACKAGE=/tmp/hyperg.tar.gz
declare -r ELECTRON_PACKAGE="electron.tar.gz"

# Questions
declare -i INSTALL_DOCKER=0
declare -i INSTALL_NVIDIA_DOCKER=0
declare -i INSTALL_NVIDIA_MODPROBE=0
declare -i INSTALL_GVISOR_RUNTIME=0

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
    echo -e "\e[91m$@\e[39m" >&2
}

# @brief print warning message
# @param warning message
function warning_msg()
{
    echo -e "\e[93m$@\e[39m"
}

# @brief print info message
# @param info message
function info_msg()
{
    echo -e "\e[92m$@\e[39m"
}


# @brief ask user
# @param question
# @return 1 if answer is 'yes', 0 if 'no'
function ask_user()
{
    while [[ 1 ]]; do
        read -p "$@ " yn
        case ${yn} in
            y|Y ) return 1;;
            n|N ) return 0;;
            * ) warning_msg "Please answer yes or no.";;
        esac
    done
}

# @brief parse the JSON file and find the latest release binary URL
# @param JSON URL
# @return release binary URL
function release_url()
{
    code=$(cat <<EOC
import sys, json;
j = json.load(sys.stdin);
k = 'browser_download_url';
print([asset[k] for entry in j
           if 'assets' in entry
       for asset in entry['assets']
           if asset[k].find('linux') != -1
      ][0])
EOC
)
    json=$(wget -qO- --header='Accept: application/json' $1)
    echo ${json} | ${PYTHON} -c "${code}"
}

function installed_package_version()
{
    echo $(dpkg -l 2>/dev/null | grep "$@\s" | grep -E 'hi|ii' | head -1 | awk '{print $3}')
}

# @brief check if dependencies (Docker, nvidia-docker + nvidia-modprobe)
# are installed and set proper 'global' variables
function check_dependencies()
{
    # Check if docker is installed
    $(docker -v > /dev/null 2>&1)
    if [[ $? -ne 0 ]]; then
        info_msg "To be installed: docker-ce"
        INSTALL_DOCKER=1
    fi

    # Check if nvidia-docker2 is installed
    if [[ -z "$(installed_package_version nvidia_docker2)" ]]; then
        if [[ -z "$(lspci | grep -i nvidia)" ]]; then
            warning_msg "Not supported: nvidia-docker2: incompatible device"
        elif [[ ! -z "$(lsmod | grep -i nouveau)" ]]; then
            warning_msg "Not supported: nvidia-docker2: please install the proprietary driver"
        elif [[ -z "$(lsmod | grep -i nvidia)" ]]; then
            warning_msg "Not supported: nvidia-docker2: no compatible driver found"
        else
            ask_user "nvidia-docker2 not found. Do you want to install it? (y/n)"
            if [[ $? -eq 1 ]]; then
                info_msg "To be installed: nvidia-docker2"
            fi

            INSTALL_NVIDIA_DOCKER=$?
        fi
    else
        info_msg "Already installed: nvidia-docker2"
    fi

    # Installer will overwrite existing /usr/local/bin/runsc 
    INSTALL_GVISOR_RUNTIME=1

    # Check for nvidia-modprobe
    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then
        if [[ -z "$(which nvidia-modprobe)" ]]; then
            INSTALL_NVIDIA_MODPROBE=1
        else
            info_msg "Already installed: nvidia-modprobe"
        fi
    fi
}

function nvidia_docker_dependency()
{
    code=$(cat <<EOC
# =================================================================
import sys
import re
from distutils.version import LooseVersion

packages = sys.stdin.read().split('\n')
candidate = None

version_re = re.compile('docker-ce \\(= ([a-z0-9:\\~\\.\\-]+)\\)')
inner_re = re.compile('(.*:)?([0-9\\.]+).*')


def get_version(line):
    version_match = version_re.search(line)
    if not version_match:
        return None

    version_str = version_match.groups()[0]
    inner_match = inner_re.search(version_str)
    if not inner_match:
        return None

    inner = inner_match.groups()[1]
    return version_str, LooseVersion(inner)

def is_newer(version):
    if not version:
        return False
    if not candidate:
        return True
    return version[1] > candidate[1]


for line in packages:
    if line.startswith('Depends'):
        version = get_version(line)
        try:
            if is_newer(version):
                candidate = version
        except:
            pass

if candidate:
    print(candidate[0])
# =================================================================
EOC
)

    PACKAGES=$(wget -qO- $1)
    echo "${PACKAGES}" | ${PYTHON} -c "${code}"
}

# @brief Install/Upgrade required dependencies
function install_dependencies()
{
    sudo id &> /dev/null
    if [[ $? -ne 0 ]]; then
        error_msg "This installer requires sudo privileges"
        exit 1
    fi

    declare -a packages=( openssl pkg-config libjpeg-dev libopenexr-dev \
               libssl-dev autoconf libgmp-dev libtool libffi-dev \
               libgtk2.0-0 libxss1 libgconf-2-4 libnss3 libasound2 \
               libfreeimage3 )

    declare -a docker_packages=("docker-ce" "docker.io" "docker-engine")

    for docker_package in "${docker_packages[@]}"; do
       docker_version=$(installed_package_version ${docker_package})
       if [[ ! -z "${docker_version}" ]]; then
           break
       fi
    done

    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then

        INSTALL_DOCKER=1
        remove_docker=0

        distribution=$(. /etc/os-release;echo ${ID}${VERSION_ID})
        nv_docker_version=$(nvidia_docker_dependency https://nvidia.github.io/nvidia-docker/${distribution}/amd64/Packages)

        wget -qO- https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -

        wget -qO- https://nvidia.github.io/nvidia-docker/${distribution}/nvidia-docker.list | \
            sudo tee /etc/apt/sources.list.d/nvidia-docker.list

        if [[ -z "${nv_docker_version}" ]]; then
            warning_msg "Cannot read nvidia-docker2 docker dependency version"
        elif [[ -z "${docker_version}" ]]; then
            warning_msg "Forcing installation: docker-ce=${nv_docker_version}"
            warning_msg "\t required by: nvidia-docker2"
        elif [[ "${docker_version}" == "${nv_docker_version}" ]]; then
            info_msg "Already installed: docker-ce=${nv_docker_version}"

            INSTALL_DOCKER=0
        else
            warning_msg "Dependency version mismatch:"
            warning_msg "\t required by: nvidia-docker2"
            warning_msg "\t dependency:  docker-ce=${nv_docker_version}"
            warning_msg "\t installed:   ${docker_package}=${docker_version}"

            remove_docker=1
        fi

        docker_version="${nv_docker_version}"
        packages+=(nvidia-docker2)
    fi

    if [[ ${INSTALL_NVIDIA_MODPROBE} -eq 1 ]]; then
        sudo apt-add-repository multiverse >/dev/null 2>&1
        packages+=(nvidia-modprobe)
    fi

    if [[ ${remove_docker} -eq 1 ]]; then

        ask_user "The installer will now remove any existing Docker installations. Do you want to continue?"
        if [[ $? -ne 1 ]]; then
            warning_msg "Aborting"
            exit 1
        fi

        info_msg "Removing: docker, nvidia-docker2"
        ! sudo service docker stop > /dev/null 2>&1
        ! sudo apt-get purge -y docker-engine docker.io docker-ce docker-ce-cli nvidia-docker2 > /dev/null 2>&1
    fi

    if [[ ${INSTALL_DOCKER} -eq 1 ]]; then
        packages+=( apt-transport-https \
                    ca-certificates \
                    software-properties-common )
        wget -qO- https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
        sudo add-apt-repository \
            "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) \
            stable"

        if [[ -z "${docker_version}" ]]; then
            packages+=(docker-ce)
        else
            packages+=("docker-ce=${docker_version}")
        fi
    fi

    sudo apt-get update >/dev/null 2>&1
    echo -e "\e[91m"
    info_msg "Installing: ${packages[*]}"
    sudo apt-get install -q -y ${packages[*]} >/dev/null

    if [[ $? -ne 0 ]]; then
        error_msg "Unable to install the required packages. Aborting."
        error_msg "Please make sure that there is no system update running and there are no broken packages."
        return 1
    fi

    if [[ ${INSTALL_NVIDIA_DOCKER} -eq 1 ]]; then
        ! sudo apt-mark hold nvidia-docker2 docker-ce
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
        info_msg "Downloading: HyperG=${hyperg_release}"
        wget --show-progress -qO- ${hyperg} > ${HYPERG_PACKAGE}
        info_msg "Installing HyperG into $HOME/hyperg"
        [[ -d $HOME/hyperg ]] && rm -rf $HOME/hyperg
        tar -xvf ${HYPERG_PACKAGE} >/dev/null
        [[ "$PWD" != "$HOME" ]] && mv hyperg $HOME/
        [[ ! -f /usr/local/bin/hyperg ]] && sudo ln -s $HOME/hyperg/hyperg /usr/local/bin/hyperg
        [[ ! -f /usr/local/bin/hyperg-worker ]] && sudo ln -s $HOME/hyperg/hyperg-worker /usr/local/bin/hyperg-worker
        rm -f ${HYPERG_PACKAGE} &>/dev/null
    fi

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

    if [[ ${INSTALL_GVISOR_RUNTIME} -eq 1 ]]; then
        wget https://storage.googleapis.com/gvisor/releases/nightly/2019-04-01/runsc
        wget https://storage.googleapis.com/gvisor/releases/nightly/2019-04-01/runsc.sha512
        sha512sum -c runsc.sha512
        rm runsc.sha512

        # Add runtime configuration
        sudo mkdir -p /etc/docker
        sudo python << EOF
import json

runtime_config = {
    'path': '/usr/local/bin/runsc'
}

with open('/etc/docker/daemon.json', 'w+') as f:
    try:
        daemon_json = json.load(f)
    except ValueError as e:
        daemon_json = {}

    if not 'runtimes' in daemon_json:
        daemon_json['runtimes'] = {}

    daemon_json['runtimes']['runsc'] = runtime_config
    json.dump(daemon_json, f, indent=4)
EOF
        chmod a+x runsc
        sudo mv runsc /usr/local/bin
        sudo service docker restart || true
    fi

}

# @brief Download latest Golem package (if package wasn't passed)
# @return 1 if error occurred, 0 otherwise
function download_package() {
    if [[ -f "$LOCAL_PACKAGE" ]]; then
        info_msg "Local package provided, skipping downloading..."
        cp "$LOCAL_PACKAGE" "/tmp/$PACKAGE"
    else
        info_msg "Downloading: Golem"
        if [[ ${DEVELOP} -eq 0 ]]; then
            golem_url=$(release_url "https://api.github.com/repos/golemfactory/golem/releases")
        else
            golem_url=$(release_url "https://api.github.com/repos/golemfactory/golem-dev/releases")
        fi
        wget --show-progress -qO- ${golem_url} > /tmp/${PACKAGE}
    fi
    if [[ ! -f /tmp/${PACKAGE} ]]; then
        error_msg "Cannot find Golem package"
        error_msg "Contact Golem team: https://chat.golem.network/ or contact@golem.network"
        exit 1
    fi

    if [[ -f ${UI_PACKAGE} ]]; then
        info_msg "UI package provided, skipping downloading..."
        cp ${UI_PACKAGE} /tmp/${ELECTRON_PACKAGE}
    else
        info_msg "Downloading: Golem GUI"
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
    ELECTRON_DIR=$(find . -maxdepth 1 -name "golem-electron-beta-linux*" -type d -print | head -n1)
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
    if [[ ${DEPS_ONLY} -eq 1 ]]; then
        info_msg "Finished installing dependencies"
        return
    fi
    install_golem
    result=$?
    if [[ ${result} -ne 0 ]]; then
        error_msg "Installation failed"
    else
        if [[ ${INSTALL_DOCKER} -eq 1 ]]; then
            warning_msg "You need to restart your PC to finish installation"
        else
            info_msg "Installation complete"
        fi
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
