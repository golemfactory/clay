#!/bin/bash -e

bundle_version=5
resource_dir="$(dirname "${BASH_SOURCE[0]}")/../resources"
package_name="transcoding-video-bundle-v$bundle_version.zip"
package_url="http://builder.concent.golem.network/download/$package_name"

mkdir --parents "$resource_dir/videos/"
cd "$resource_dir"

curl --remote-name "$package_url"
unzip "$package_name" -d videos/

# The unpacked files are inside a transcoding-video-bundle/ directory.
# Move them out of it.
mv "videos/transcoding-video-bundle/"* "videos/"
rm -r "videos/transcoding-video-bundle/"

# TODO: Add an option to allow user to tell us not to delete the archive.
rm "$package_name"
