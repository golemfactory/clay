# Buildbot mac worker role

Install all dependencies for the golem project unit test.

Steps to install TRAVIS tests

- Get mac in cloud
- Login via VNC
- Enable SSH
- `ssh-copy-id` to the server
- Set become password in vault
- Update static host for this mac
- Update buildbot-master firewall rules to allow the new mac

- Install roles `cd scripts/ci; ansible-galaxy install -r requirements.yml ./roles/` 
- Run playbook
- Click install command line tools on remote machine (check if needed)
- 


Required before running ALL tests:
- clean osx 10.10
- xcode 7.2.1
- enable ssh for admin user
- as running admin user
 - `$ sudo chown -R $(whoami):admin /usr/local`
 - `$ sudo xcode-select --install`
 - `$ sudo xcode-select -switch /`





export TRAVIS=true

 https://superuser.com/questions/318809/linux-os-x-tar-incompatibility-tarballs-created-on-os-x-give-errors-when-unt
