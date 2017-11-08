# Buildbot mac worker role

Install all dependencies for the golem project unit test.

Required before running:
- clean osx 10.10
- xcode 7.2.1
- enable ssh for admin user
- as running admin user
 - `$ sudo chown -R $(whoami):admin /usr/local`
 - `$ sudo xcode-select --install`
 - `$ sudo xcode-select -switch /`





export TRAVIS=true

 https://superuser.com/questions/318809/linux-os-x-tar-incompatibility-tarballs-created-on-os-x-give-errors-when-unt
