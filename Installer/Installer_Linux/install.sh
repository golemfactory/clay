#!/bin/bash
trap "exit" INT

# Meta information

SCRIPT_VERSION="0.1.0"
SCRIPT_AUTHOR="Karol Tomala"

# Default variables

DEBUG=0
DOWNLOAD_PROGRESS=0
CLEANUP_TMP=1
INSTALL_DEVELOP=0
INSTALL_OPTIONAL=0
NO_EXTENSIONS_INSTALL=0
EXTENSION_HASH_CHECK=1

EXTRA_PACKAGES=()
REMOVE_EXTRA_PACKAGES=()
HOLD_PACKAGES=()
UNHOLD_PACKAGES=()
AFTER_DEPENDENCY_INSTALL_FUNCTIONS=()

DOWNLOADERS=( curl wget )
DOWNLOAD_TMP_PATH=/tmp
MANIFEST_URL='https://golem-releases.cdn.golem.network/manifest.yml'
MANIFEST_FILE='golem_releases_manifest.yml'

SUPPORTED_OS=( linux )

MANIFEST_RELEASES_PREFIX="golem_releases"
MANIFEST_RELEASES_LATEST="${MANIFEST_RELEASES_PREFIX}_latest"
MANIFEST_RELEASES_PUBLISHED="${MANIFEST_RELEASES_PREFIX}_published"
MANIFEST_RELEASES_DESCRIPTIONS="${MANIFEST_RELEASES_PREFIX}_descriptions"

INSTALL_DESTINATION_PREFIX=/opt/golem
INSTALL_SYMLINK_PREFIX=/usr/local/bin

TMP_ERR_LOG=/tmp/golem_install_script.err.log

SKIP_DEPS_UPDATE=0
OVERWRITE=1

TYPEPRINT_DELAY=.005

DEFAULT_COMPONENT_STATUS="mandatory"

# Docker variables

DOCKER_GPG_KEY="https://download.docker.com/linux/ubuntu/gpg"
DOCKER_VERSION=
INSTALL_DOCKER=1
REMOVE_DOCKER=0
DOCKER_CONFIG_FILE="/etc/docker/daemon.json"

# Character maps

CHAR_UNICODE_SPIN='⡄⡆⡇⠇⠃⠋⠉⠙⠘⠚⠒⠖⠆⠦⠤⢤⢠⣠⣀⣄'
CHAR_ASCII_SPIN='-\|/'

# Message functions

err_msg () { local arg_msg=$*; echo "ERROR: $arg_msg" >&2; exit 1; }
warn_msg () { local arg_msg=$*; echo "WARNING: $arg_msg" >&2; }
debug_msg () { local arg_msg=$*; [ $DEBUG -eq 1 ] && echo "DEBUG: $arg_msg" >&2; }
info_msg () { local arg_msg=$*; echo "$arg_msg"; }
spinner_msg () {
  local arg_msg=$*
  if [ "$UNICODE_SUPPORT" == "Y" ]; then
    local bullet="⬝"
    local tick="✓"
    local cross="✕"
  else
    local bullet="*"
    local tick="+"
    local cross="-"
  fi
  printf " $bullet $arg_msg "
  spinner
  [ $PID_STATUS -eq 0 ] && printf "$tick\n" || printf "$cross\n"
  return $PID_STATUS
}

typeprint () {
  local x=$@
  for((i=0;i<${#x};i++));do echo -n "${x:$i:1}";sleep $TYPEPRINT_DELAY;done;echo
}

# Info functions

print_banner () {
  typeprint "Golem Linux Installer version $SCRIPT_VERSION. Golem Factory GmbH 2019"
}

# Helper functions

test_unicode () {
  echo -ne "\xe2\x88\xb4\033[6n\033[1K\r"
  read -d R foo
  echo -ne "\033[1K\r"
  echo -e "${foo}" | cut -d \[ -f 2 | cut -d";" -f 2 | (
    read UNICODE
    [ $UNICODE -eq 2 ] && return 0
    [ $UNICODE -ne 2 ] && return 1
  )
}

run_tput () {
  local arg_1=$1
  [ $TPUT_UNAVAILABLE -ne 0 ] && return 1
  $TPUT_RUNTIME "$arg_1"
  return 0
}

spinner () {
  # Process Id of the previous running command
  local pid=$!
  run_tput civis
  [ "$UNICODE_SUPPORT" == "Y" ] && spin="$CHAR_UNICODE_SPIN" || spin="$CHAR_ASCII_SPIN"
  printf ' '
  local i=0
  while kill -0 $pid 2>/dev/null
  do
    i=$(( (i+1) % ${#spin} ))
    printf "\b${spin:$i:1}"
    sleep .1
  done
  printf "\b \b"
  run_tput cnorm
  wait $pid
  PID_STATUS=$?
}

function_exists () {
  declare -f -F $1 > /dev/null
  return $?
}

parse_yaml () {
   local prefix=$2
   local s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
   sed -ne "s|^\($s\):|\1|" \
        -e "s|^\($s\)\($w\)$s:$s[\"']\(.*\)[\"']$s\$|\1$fs\2$fs\3|p" \
        -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  $1 |
   awk -F$fs '{
      indent = length($1)/2;
      vname[indent] = $2;
      for (i in vname) {if (i > indent) {delete vname[i]}}
      if (length($3) > 0) {
         vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
         printf("%s%s%s=\"%s\"\n", "'$prefix'",vn, $2, $3);
      }
   }'
}

contains_element () {
  local e match="$1"
  shift
  for e; do [[ "$e" == "$match" ]] && return 0; done
  return 1
}

cleanup_tmp () {
  [ $CLEANUP_TMP -ne 1 ] && return
  rm -f $DOWNLOAD_TMP_PATH/$MANIFEST_FILE
}

# Downloader functions

download_curl () {
  local arg_url="$1"
  local arg_dst_file="$2"
  if [ $DOWNLOAD_PROGRESS -eq 1 ]; then
    $DOWNLOADER_RUNTIME -f -L --output "$DOWNLOAD_TMP_PATH/$arg_dst_file" --progress-bar "$arg_url"
    res=$?
  else
    $DOWNLOADER_RUNTIME -f -L -s --output "$DOWNLOAD_TMP_PATH/$arg_dst_file" "$arg_url"
    res=$?
  fi
  sleep 1
  return $res
}

download_wget () {
  local arg_url="$1"
  local arg_dst_file="$2"
  if [ $DOWNLOAD_PROGRESS -eq 1 ]; then
    $DOWNLOADER_RUNTIME --show-progress -q -O "$DOWNLOAD_TMP_PATH/$arg_dst_file" "$arg_url"
    res=$?
  else
    $DOWNLOADER_RUNTIME -q -O "$DOWNLOAD_TMP_PATH/$arg_dst_file" "$arg_url"
    res=$?
  fi
  return $res
}

download () {
  local arg_url=$1
  local arg_dst_file=$2
  local downloader_name=$( basename $DOWNLOADER_RUNTIME )
  local function_name="download_${downloader_name}"
  if ! function_exists $function_name; then
    err_msg "No such function: ${function_name}."
  fi
  debug_msg "Downloading $arg_url as file $DOWNLOAD_TMP_PATH/$arg_dst_file"
  $function_name "$arg_url" "$arg_dst_file"
  return $?
}

# Self-check functions

check_unicode () {
  test_unicode
  local RC=$?
  export UNICODE_SUPPORT=`[ $RC -eq 0 ] && echo "Y" || echo "N"`
  unset test_unicode
}

check_which () {
  $( which bash > /dev/null 2>&1 )
  return $?
}

check_app_exists () {
  local app_name=$1
  which $app_name > /dev/null 2>&1
  return $?
}

check_downloader () {
  debug_msg "Checking downloader availability"
  local exit_status=1
  for downloader in ${DOWNLOADERS[@]}; do
    local downloader_path=$( which $downloader 2>/dev/null; exit_status=$? )
    [ $exit_status -eq 0 ] && break
  done
  [ "$downloader_path" == "" ] && return 1
  echo $downloader_path
  return 0
}

check_tput () {
  debug_msg "Checking tput availability"
  local tput_path=$( which tput 2>/dev/null )
  res=$?
  echo $tput_path
  return $res
}

check_os () {
  local os_name=$( uname -s | awk '{print tolower($0)}' )
  local supported_os=$( echo ${SUPPORTED_OS[@]} | awk '{print tolower($0)}' )
  contains_element $os_name ${supported_os[@]} || err_msg "Installer does not support '$os_name' operating system."
}

check_distribution () {
  local distro_name=$( lsb_release -is 2>/dev/null | awk '{print tolower($0)}' )
  echo $distro_name
}

check_distribution_version () {
  local distro_version=$( lsb_release -rs 2>/dev/null | awk '{print tolower($0)}' )
  echo $distro_version
}

self_check () {
  debug_msg "Self check"
  check_unicode
  check_which || err_msg "No 'which' found in PATH."

  apps_to_check=( basename sed awk grep uname lsb_release cut uniq tr tar sha256sum )
  for app_name in ${apps_to_check[@]}; do
    check_app_exists "$app_name" || err_msg "No '$app_name' found in PATH."
  done

  check_os
  DOWNLOADER_RUNTIME=$( check_downloader )
  [ $? -ne 0 ] && err_msg "No suitable downloader found (one of: ${DOWNLOADERS[@]})."
  TPUT_RUNTIME=$( check_tput )
  TPUT_UNAVAILABLE=$?
}

cache_sudo () {
  # Just for getting password cached
  sudo ls > /dev/null 2>&1
}

# Manifest functions

manifest_check () {
  debug_msg "Checking manifest"
  local manifest_error="Manifest has improper format. Perhaps newer install script is required?"
  eval $( parse_yaml "$DOWNLOAD_TMP_PATH/$MANIFEST_FILE" )
  # local var_name="${MANIFEST_DEPENDENCY_PREFIX}_ubuntu_default"
  # [ -z ${!var_name+x} ] && err_msg "$manifest_error"
  [ -z ${golem_releases_latest+x} ] && err_msg "$manifest_error"
  [ -z ${golem_releases_published+x} ] && err_msg "$manifest_error"
  local release_descriptions=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}" ) )
  [ ${#release_descriptions[@]} -eq 0 ] && err_msg "$manifest_error"
}

retrieve_manifest () {
  debug_msg "Retrieving manifest"
  rm -f $DOWNLOAD_TMP_PATH/${MANIFEST_FILE} > /dev/null 2>&1
  download "${MANIFEST_URL}" "${MANIFEST_FILE}" &
  spinner_msg "Downloading manifest" || err_msg "Failed downloading manifest."
  [ ! -f $DOWNLOAD_TMP_PATH/$MANIFEST_FILE ] && err_msg "Manifest file does not exist."
  manifest_check
}

# Dependency functions

failed_dependency_install () {
  local err_message=$1
  exec 2>&6 6>&-
  [ -f $TMP_ERR_LOG ] && echo -e "\nCommand returned errors:\n------------------------" && cat $TMP_ERR_LOG >&2 && rm -f $TMP_ERR_LOG && echo
  err_msg "${err_message}"
}

install_dependencies_ubuntu () {
  local dependencies=$@
  debug_msg "Installing dependencies for Ubuntu"
  exec 6>&2 2>$TMP_ERR_LOG
  if [ ${SKIP_DEPS_UPDATE} -eq 0 ]; then
    $( sudo apt-get update -y > /dev/null ) &
    spinner_msg "Updating apt repositories" || failed_dependency_install "Failed updating apt repositories."
  fi
  if [[ ! -z "$UNHOLD_PACKAGES" && ${#UNHOLD_PACKAGES[@]} -gt 0 ]]; then
    $( sudo apt-mark unhold ${UNHOLD_PACKAGES[@]} > /dev/null ) &
    spinner_msg "Unsetting packages hold: ${UNHOLD_PACKAGES[@]}" || failed_dependency_install "Failed packages unhold."
  fi
  if [[ ! -z "$HOLD_PACKAGES" && ${#HOLD_PACKAGES[@]} -gt 0 ]]; then
    $( sudo apt-mark unhold ${HOLD_PACKAGES[@]} > /dev/null ) &
    spinner_msg "Unsetting packages hold: ${HOLD_PACKAGES[@]}" || failed_dependency_install "Failed packages unhold."
  fi
  $( sudo apt-get install -y ${dependencies[@]} > /dev/null ) &
  spinner_msg "Installing dependencies" || failed_dependency_install "Failed dependency installation."
  if [[ ! -z "$EXTRA_PACKAGES" && ${#EXTRA_PACKAGES[@]} -gt 0 ]]; then
    $( sudo apt-get install -y ${EXTRA_PACKAGES[@]} > /dev/null ) &
    spinner_msg "Installing extra dependencies" || failed_dependency_install "Failed extra dependency installation."
  fi
  if [[ ! -z "$HOLD_PACKAGES" && ${#HOLD_PACKAGES[@]} -gt 0 ]]; then
    $( sudo apt-mark hold ${HOLD_PACKAGES[@]} > /dev/null ) &
    spinner_msg "Setting packages on hold: ${HOLD_PACKAGES[@]}" || failed_dependency_install "Failed packages hold."
  fi
  exec 2>&6 6>&-
}

install_dependencies () {
  local distro_name=$1
  local dependencies=${@:2}

  debug_msg "Installing dependencies"
  local function_name="install_dependencies_$distro_name"
  if ! function_exists $function_name; then
    err_msg "Cannot install dependencies. Distribution not supported: $distro_name. No such function: ${function_name}."
  fi
  $function_name "${dependencies[@]}"
}

resolve_dependencies () {
  local distro_name=$1
  local distro_version=$2
  local dependency_var="${MANIFEST_DEPENDENCY_PREFIX}_${distro_name}_${distro_version}"
  local references=( $( echo "${!dependency_var}" | grep -w -o -E -e "@[a-zA-Z0-9_]+" ) )
  local non_references=( $( echo "${!dependency_var}" | grep -o -P "(?:(?<=^)|(?<=\s))(?<!@)[a-zA-Z0-9-_.]+" ) )
  local result="${non_references[@]}"
  for reference in ${references[@]}; do
    local resolved_references=( $( resolve_dependencies "${distro_name}" "${reference:1}" ) )
    result+=" ${resolved_references[@]}"
  done
  echo "${result[@]}" | tr -s ' ' '\n' | sort -u | tr -s '\n' ' '
}

install_docker_ubuntu () {
  local docker_version=$1
  debug_msg "Installing docker on Ubuntu"
  exec 6>&2 2>$TMP_ERR_LOG
  $( sudo apt-get remove -y docker docker-engine docker.io > /dev/null ) &
  spinner_msg "Removing obsolete docker" || failed_dependency_install "Failed removing obsolete docker."
  if [[ ! -z "$REMOVE_DOCKER" && $REMOVE_DOCKER -eq 1 ]]; then
    $( sudo systemctl stop docker > /dev/null ) &
    spinner_msg "Stopping docker" || failed_dependency_install "Failed stopping docker."
    $( sudo apt-get remove -y docker-ce docker-ce-cli ${REMOVE_EXTRA_PACKAGES[@]} > /dev/null ) &
    spinner_msg "Removing installed docker-ce and extra packages" || failed_dependency_install "Failed removing docker-ce and extra packages."
  fi
  $( sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common > /dev/null ) &
  spinner_msg "Installing docker dependencies" || failed_dependency_install "Failed installing docker dependencies."
  $( download "$DOCKER_GPG_KEY" "docker-repo-key.gpg"; sudo apt-key add $DOWNLOAD_TMP_PATH/docker-repo-key.gpg > /dev/null ) &
  spinner_msg "Adding docker repository GPG key" || failed_dependency_install "Failed adding docker repository GPG key."
  $( sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /dev/null ) &
  spinner_msg "Adding docker repository" || failed_dependency_install "Failed adding docker repository."
  if [ $SKIP_DEPS_UPDATE -eq 0 ]; then
    $( sudo apt-get update -y > /dev/null ) &
    spinner_msg "Updating packages" || failed_dependency_install "Failed updating packages."
  fi
  local docker_version_to_install="docker-ce"
  [ ! -z "$docker_version" ] && docker_version_to_install="docker-ce=${docker_version}"
  $( sudo apt-get install -y --allow-change-held-packages ${docker_version_to_install} > /dev/null ) &
  spinner_msg "Installing docker-ce" || failed_dependency_install "Failed installing docker-ce."
  if [ -z "${SUDO_USER}" ]; then
    $( sudo usermod -aG docker ${USER} ) &
  else
    $( sudo usermod -aG docker ${SUDO_USER} ) &
  fi
  spinner_msg "Add user to docker group." || failed_dependency_install "Cannot add user to docker group."
  $( sudo systemctl restart docker ) &
  spinner_msg "Restarting docker" || failed_dependency_install "Failed to restart docker."
  $( sudo docker run hello-world > /dev/null 2>&1 ) &
  spinner_msg "Testing docker is running" || failed_dependency_install "Docker cannot run hello-world. Testing failed."
  exec 2>&6 6>&-
}

install_docker () {
  local distro_name=$1
  local docker_version=$2
  local function_name="install_docker_$distro_name"
  if ! function_exists $function_name; then
    err_msg "Cannot install docker. Distribution not supported: $distro_name. No such function: ${function_name}."
  fi
  $function_name "${docker_version}"
}

check_package_installed_version_ubuntu () {
  echo $(dpkg -l 2>/dev/null | grep "$@\s" | grep -E 'hi|ii' | head -1 | awk '{print $3}')
}

check_package_installed_version () {
  local distro_name=$1
  local package_name=$2
  local function_name="check_package_installed_version_$distro_name"
  if ! function_exists $function_name; then
    err_msg "Cannot check package installed. Distribution not supported: $distro_name. No such function: ${function_name}."
  fi
  $function_name "${package_name}"
}

check_distro_installer_ubuntu () {
  local ubuntu_installer_components=( apt-get add-apt-repository apt-key )
  for installer_component in ${ubuntu_installer_components[@]}; do
    check_app_exists "$installer_component" || err_msg "No '$installer_component' found in PATH."
  done
}

check_distro_installer () {
  local distro_name=$1
  local function_name="check_distro_installer_$distro_name"
  if ! function_exists $function_name; then
    err_msg "Cannot check distro installer. Distribution not supported: $distro_name. No such function: ${function_name}."
  fi
  $function_name
}

parse_dependencies () {
  debug_msg "Parse dependencies"
  local distro_name=$( check_distribution )
  local supported_distros=( $( compgen -A variable | grep "${MANIFEST_DEPENDENCY_PREFIX}_" | cut -d_ -f8 | uniq ) )
  debug_msg "${MANIFEST_DEPENDENCY_PREFIX}"
  debug_msg "Script supported distributions: ${supported_distros[@]}"
  debug_msg "Found distribution name: $distro_name"
  if ! contains_element "$distro_name" "${supported_distros[@]}"; then
    err_msg "Linux distribution '$distro_name' is not supported by this installer."
  fi
  local distro_version=$( check_distribution_version | tr -s '.' '_' )
  local supported_versions=( $( compgen -A variable | grep "${MANIFEST_DEPENDENCY_PREFIX}_${distro_name}_" | cut -d_ -f9- | uniq ) )
  if ! contains_element "$distro_version" "${supported_versions[@]}"; then
    if ! contains_element "default" "${supported_versions[@]}"; then
      err_msg "Manifest file does not have dependency definition for this distribution version, nor default one."
    else
      distro_version="default"
    fi
  fi
  debug_msg "Supported distribution version: $distro_version"
  check_distro_installer "$distro_name"
  [ $INSTALL_DOCKER -ne 0 ] && install_docker "$distro_name" "${DOCKER_VERSION}"
  local dependencies=( $( resolve_dependencies "${distro_name}" "$distro_version" ) )
  install_dependencies "$distro_name" "${dependencies[@]}"
  for after_dependency_func in ${AFTER_DEPENDENCY_INSTALL_FUNCTIONS[@]}; do
    ${after_dependency_func} "$distro_name"
  done
}

# Extensions install

parse_extensions () {
  debug_msg "Parse extensions for $install_release_version"
  local install_release_version=$1
  local extensions_list=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_extensions" | cut -d_ -f8 | uniq ) )
  [ ${#extensions_list[@]} -eq 0 ] && debug_msg "No extensions found for release in manifest." && return

  for extension in ${extensions_list[@]}; do
    local extension_script_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_extensions_${extension}_script"
    local extension_hash_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_extensions_${extension}_hash"
    [[ -z ${extension_script_var} || "${!extension_script_var}" == "" ]] && warn_msg "Extension '${extension}' has no script defined in manifest. Skipping..." && continue
    if [ $EXTENSION_HASH_CHECK -eq 1 ]; then
      [[ -z ${extension_hash_var} || "${!extension_hash_var}" == "" ]] && warn_msg "Extension '${extension}' has no hash defined in manifest. Skipping..." && continue
    fi

    local extension_script=${!extension_script_var}
    local extension_file=${extension_script##*/}
    download "${extension_script}" "${extension_file}" &
    spinner_msg "Downloading install script for extension '$extension'" || { warn_msg "Failed downloading extension script. Skipping..." && continue; }

    if [ $EXTENSION_HASH_CHECK -eq 1 ]; then
      local extension_file_hash=$( sha256sum ${DOWNLOAD_TMP_PATH}/${extension_file} | cut -d\  -f1 )
      [ "$extension_file_hash" != "${!extension_hash_var}" ] && warn_msg "Extension hash '${extension}' mismatch. Skipping..." && continue
    fi

    source "${DOWNLOAD_TMP_PATH}/${extension_file}"

  done
}

# Installation functions

install_release () {
  local release_file=$1
  local release_version=$2
  local release_links=${@:3}

  debug_msg "Installing release"
  exec 6>&2 2>$TMP_ERR_LOG
  if [ ! -d $INSTALL_DESTINATION ]; then
    sudo mkdir -p $INSTALL_DESTINATION > /dev/null || failed_dependency_install "Cannot create directory: $INSTALL_DESTINATION"
  else
    [ $OVERWRITE -ne 1 ] && failed_dependency_install "Installation destination path already exists: $INSTALL_DESTINATION"
    warn_msg "Installation destination path already exists! Overwriting."
  fi
  $( sudo tar -C $INSTALL_DESTINATION -xzf $DOWNLOAD_TMP_PATH/$release_file --strip-components 1 > /dev/null ) &
  spinner_msg "Extracting release archive ${release_file} to ${INSTALL_DESTINATION}" || failed_dependency_install "Failed extracting archive '${release_file}'."

  if [ ${#release_links[@]} -ne 0 ]; then
    for release_link in ${release_links[@]}; do
      [ ! -f ${INSTALL_DESTINATION}/$release_link ] && warn_msg "Cannot symlink ${release_link}. File not found." && continue
      $( sudo ln -fs ${INSTALL_DESTINATION}/$release_link $INSTALL_SYMLINK_PREFIX ) &
      spinner_msg "Symlinking ${release_link} to ${INSTALL_SYMLINK_PREFIX}" || failed_dependency_install "Failed symlinking '${release_link}'."
    done
  fi
  exec 2>&6 6>&-
}

install_component () {
  local component_file=$1
  local component_name=$2
  local component_destination=$3
  [[ -z ${component_destination+x} || "$component_destination" == "" ]] && component_destination=$INSTALL_DESTINATION
  local component_links=${@:4}

  debug_msg "Installing release component $component_name"
  exec 6>&2 2>$TMP_ERR_LOG
  if [ ! -d $component_destination ]; then
    sudo mkdir -p $component_destination > /dev/null || failed_dependency_install "Cannot create directory: $component_destination"
  fi
  $( sudo tar -C $component_destination -xzf $DOWNLOAD_TMP_PATH/$component_file --strip-components 1 > /dev/null ) &
  spinner_msg "Extracting component archive ${component_file} to ${component_destination}" || failed_dependency_install "Failed extracting archive '${component_file}'."

  if [ ${#component_links[@]} -ne 0 ]; then
    for component_link in ${component_links[@]}; do
      [ ! -f ${component_destination}/$component_link ] && warn_msg "Cannot symlink ${component_link}. File not found." && continue
      $( sudo ln -fs ${component_destination}/$component_link $INSTALL_SYMLINK_PREFIX ) &
      spinner_msg "Symlinking ${component_link} to ${INSTALL_SYMLINK_PREFIX}" || failed_dependency_install "Failed symlinking '${component_link}'."
    done
  fi
  exec 2>&6 6>&-
}

parse_releases () {
  local install_version=$1
  local release_latest=${!MANIFEST_RELEASES_LATEST}
  [[ -z ${install_version+x} || "$install_version" == "" ]] && install_version=$release_latest
  local release_published=( ${!MANIFEST_RELEASES_PUBLISHED} )
  contains_element $install_version ${release_published[@]} || err_msg "Manifest does not have Golem release '$install_version' in published versions."
  local release_descriptions=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}" | cut -d_ -f4-6 | uniq ) )
  [ ${#release_descriptions[@]} -eq 0 ] && err_msg "Manifest does not have at least one release version description."
  local release_descriptions_versions=( $( echo ${release_descriptions[@]} | tr -s '_' '.' ) )
  contains_element $release_latest ${release_descriptions_versions[@]} || err_msg "Manifest has latest release set, but no release description found."
  contains_element $install_version ${release_descriptions_versions[@]} || err_msg "Manifest has no release '$install_version' description."
  local install_release_version=$( echo $install_version | tr -s '.' '_' )

  local release_description=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}" ) )
  local release_status_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_status"
  contains_element $release_status_var ${release_description[@]} || err_msg "Release description for version '$install_version' does not have 'status'."
  local release_status=${!release_status_var}
  [[ "$release_status" != "release" && $INSTALL_DEVELOP -ne 1 ]] && err_msg "You are trying to install development version, but no --develop flag was specified."

  local release_url_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_url"
  contains_element $release_url_var ${release_description[@]} || err_msg "Release description for version '$install_version' does not have 'url'."
  local release_url=${!release_url_var}
  local release_file=${release_url##*/}

  local release_links=()
  local release_links_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_links"
  [[ -z $release_links_var || "${!release_links_var}" == "" ]] || release_links=( ${!release_links_var} )

  MANIFEST_DEPENDENCY_PREFIX="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_dependencies"

  parse_extensions "${install_release_version}"

  parse_dependencies

  $( download "${release_url}" "${release_file}" ) &
  spinner_msg "Downloading release ${install_version}" || err_msg "Failed downloading release '${install_version}'."

  INSTALL_DESTINATION=$INSTALL_DESTINATION_PREFIX/$install_version

  install_release "$release_file" "$install_version" "${release_links[@]}"

  local component_install=0
  local release_components_vars=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components" ) )
  [ ${#release_components_vars[@]} -eq 0 ] && component_install=0 || component_install=1

  if [ $component_install -eq 1 ]; then
    local release_components=( $( compgen -A variable | grep "${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components_" | cut -d_ -f8 | uniq ) )
    for release_component in ${release_components[@]}; do
      local release_component_url_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components_${release_component}_url"
      local release_component_url=${!release_component_url_var}
      local release_component_file=${release_component_url##*/}

      local release_component_path_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components_${release_component}_path"
      local release_component_path=""
      [ -z ${release_component_path_var+x} ] || release_component_path=$INSTALL_DESTINATION/${!release_component_path_var}

      local release_component_links_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components_${release_component}_links"
      local release_component_links=()
      [ -z ${release_component_links_var+x} ] || release_component_links="${!release_component_links_var}"

      local release_component_status_var="${MANIFEST_RELEASES_DESCRIPTIONS}_${install_release_version}_components_${release_component}_status"
      local release_component_status=$DEFAULT_COMPONENT_STATUS
      [[ -z ${release_component_status_var+x} || "${!release_component_status_var}" == "" ]] || release_component_status="${!release_component_status_var}"

      local release_component_install=1
      [[ "$release_component_status" == "optional" && $INSTALL_OPTIONAL -eq 0 ]] && release_component_install=0 && warn_msg "Component ${release_component} is optional. Skipping... If you want to install it, rerun installer with --optional."

      if [ $release_component_install -eq 1 ]; then
        $( download "${release_component_url}" "${release_component_file}" ) &
        spinner_msg "Downloading install component ${release_component}" || err_msg "Failed downloading install component '${release_component_file}'."

        install_component "$release_component_file" "$release_component" "$release_component_path" "${release_component_links[@]}"
      fi
    done
  fi
}

# Option parsing functions

print_usage () {
  echo "Usage: $0 [-h] [-d][-D][-m URL][-o][-O][-t TMP][-V VER]"
}

print_help () {
  print_banner
  echo -e "Options:"
  echo -e "  -h --help              Show help."
  echo -e "  -d --develop           Install development version."
  echo -e "  -D --debug             Show debug messages."
  echo -e "  -E --no-extensions     Do not try to install extensions."
  echo -e "  -m --manifest-url URL  Manifest URL."
  echo -e "  -o --optional          Install optional components."
  echo -e "  -O --overwrite         Overwrite existing installation."
  echo -e "  -s --symlink-prefix PREFIX    Location of symlinks to binaries."
  echo -e "  --skip-deps-update     Skip dependency update."
  echo -e "  -t --temp-path TMP     Download temporary path (default: ${DOWNLOAD_TMP_PATH})."
  echo -e "  -V --version VER       Install Golem version."
}

parse_options () {
  while (( "$#" )); do
    case "$1" in
      '-h' | '--help')
        print_help
        exit 1
        ;;
      '-d' | '--develop')
        INSTALL_DEVELOP=1
        ;;
      '-D' | '--debug')
        DEBUG=1
        ;;
      '-E' | '--no-extensions')
        NO_EXTENSIONS_INSTALL=1
        ;;
      '-o' | '--optional')
        INSTALL_OPTIONAL=1
        ;;
      '-O' | '--overwrite')
        OVERWRITE=1
        ;;
      '-m' | '--manifest-url')
        shift
        [[ -z $1 || "$1" == "" || "${1:0:1}" == "-" ]] && err_msg "--manifest-url requires URL argument."
        MANIFEST_URL="$1"
        ;;
      '-s' | '--symlink-prefix')
        shift
        [[ -z $1 || "$1" == "" || "${1:0:1}" == "-" ]] && err_msg "--symlink-prefix requires PREFIX argument."
        INSTALL_SYMLINK_PREFIX="$1"
        ;;
      '--skip-deps-update')
        SKIP_DEPS_UPDATE=1
        ;;
      '-V' | '--version')
        shift
        [[ -z $1 || "$1" == "" || "${1:0:1}" == "-" ]] && err_msg "--version requires VER argument."
        VERSION_TO_INSTALL=$1
        ;;
      '-t' | '--temp-path')
        shift
        [[ -z $1 || "$1" == "" || "${1:0:1}" == "-" ]] && err_msg "--temp-path requires TMP argument."
        DOWNLOAD_TMP_PATH=$1
        [ ! -d $DOWNLOAD_TMP_PATH ] && err_msg "Temporary path '$DOWNLOAD_TMP_PATH' does not exist."
        ;;
      *)
        print_usage
        err_msg "ERROR: Unknown option: $1"
        exit 1
        ;;
    esac
    shift
  done
}

# Main function

main () {
  parse_options $@
  print_banner
  self_check
  cache_sudo
  retrieve_manifest
  parse_releases
  info_msg "Golem has been installed succesfully."
}

main $@
