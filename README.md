# Golem

[![AppVeyor](https://ci.appveyor.com/api/projects/status/ieb6fm74e0f74qm1?svg=true)](https://ci.appveyor.com/project/golemfactory/golem)
[![CircleCI](https://circleci.com/gh/golemfactory/golem.svg?style=shield)](https://circleci.com/gh/golemfactory/golem)
[![codecov](https://codecov.io/gh/golemfactory/golem/branch/develop/graph/badge.svg)](https://codecov.io/gh/golemfactory/golem)

The aim of the Golem project is to create a global prosumer market for computing power, in which
producers may sell spare CPU time of their personal computers and consumers may acquire resources
for computation-intensive tasks. In technical terms, Golem is designed as a decentralised peer-to-peer
network established by nodes running the Golem client software. For the purpose of this paper we assume
that there are two types of nodes in the Golem network: requestor nodes that announce computing
tasks and compute nodes that perform computations (in the actual implementation nodes may switch
between both roles).

## Installing and testing

For Mac OS X (ver. 10.12 (Sierra) or later) follow the installation instruction from [here](https://github.com/golemfactory/homebrew-golem).
For Ubuntu (16.04 or higher) download [script](https://raw.githubusercontent.com/golemfactory/golem/develop/Installer/Installer_Linux/install.sh), make it executable `chmod +x install.sh` and run `./install.sh`.
For MS Windows 10 download the installer from [here](https://github.com/golemfactory/golem/releases/); when downloaded, just run `setup.exe`.

Then read the application description and [testing](https://github.com/golemfactory/golem/wiki/Testing) instruction.

[Golem for macOS](https://github.com/golemfactory/homebrew-golem)

[Golem Linux script](https://raw.githubusercontent.com/golemfactory/golem/develop/Installer/Installer_Linux/install.sh)

[Golem MS Windows installer](https://github.com/golemfactory/golem/releases/)

All released packages are located [here](https://github.com/golemfactory/golem/releases), however, we strongly encourage you to use prepared installers.

## Usage & troubleshoothing

Documentation for using app is here: https://docs.golem.network/

The most common problems are described in section 9: https://golem.network/documentation/09-common-issues-troubleshooting/

## Warning

Golem Project is a work in progress. Current version is an alpha stage of Brass Golem and it's not fully secured. Check [this list of issues](https://github.com/golemfactory/golem/labels/security) for more details.
Please be sure that you understand the risk before installing the software.

## License

Golem is open source and distributed under [GPLv3 license](https://www.gnu.org/licenses/gpl-3.0.html).

## Acknowledgements

Golem communicates with external technologies some of them may be downloaded and install with Golem package:
* [Docker](https://www.docker.com/)
* [FreeImage](http://freeimage.sourceforge.net/)
* [Geth](https://github.com/ethereum/go-ethereum/wiki/geth)
* [OpenExr](http://www.openexr.com/)
* [OpenSSL](https://www.openssl.org/)
* [Python3](https://www.python.org/)
* [SQLite3](https://sqlite.org/index.html)
* [Pyvmmonitor](http://pyvmmonitor.com)

Benchmarks:
* General: [Minilight](http://www.hxa.name/minilight) by Harrison Ainsworth / HXA7241 and Juraj Sukop.
* Blender: [scene-BMW](https://www.blender.org/download/demo-files/).
* LuxRender: [SchoolCorridor](http://www.luxrender.net/wiki/Show-off_pack) by Simon Wendsche.

Icons:
* [Freeline](https://www.iconfinder.com/iconsets/freeline) by Enes Dal.

## Job offers

- [C++ & Solidity Software Engineer](docs/jobs/cpp_and_solidity_software_engineer.md)

## Contact  

Help us develop the application by submitting issues and bugs. See instruction
[here](https://github.com/golemfactory/golem/wiki/Testing).

You can also send us an email to `contact@golem.network` or talk to us on [chat.golem.network](https://chat.golem.network).
