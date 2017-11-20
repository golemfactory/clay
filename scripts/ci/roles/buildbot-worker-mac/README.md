# Buildbot mac worker role

Install all dependencies for the golem project unit test.

## Steps to install TRAVIS tests

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
- Wait for the script to finish, everything should be set now. 


## Running ALL tests:
TODO: POC and add to installers
