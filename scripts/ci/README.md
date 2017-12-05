This directory contains configuration for a CI infrastructure based
on buildbot.

# Getting Started

To apply the configuration you will need to have ansible and some
extra libraries installed:

    pip install -r requirements.txt

Make sure you have your 
[AWS credentials configured](http://docs.pythonboto.org/en/latest/boto_config_tut.html)
and that your target instances are running and are properly tagged
(see Instance Identification).

To be able to configure a Windows machine, it must have WinRM configured
properly to work with ansible.  You can achieve this by logging in to the
machine and executing the
[ansible-provided PowerShell script](https://raw.githubusercontent.com/ansible/ansible/devel/examples/scripts/ConfigureRemotingForAnsible.ps1).

Site-specific configuration is read from `site_settings.yml`.
Copy the sample from `site-settings.yml.example` and fill in
parameters.

    cp site_settings.yml.example site_settings.yml
    $EDITOR site_settings.yml

To apply the configuration:

    ansible-playbook --key-file=~/.ssh/your_ssh_key -i inventory/ site.yml


# Note about HTTPS

TLS certificate handling is not automated at the moment.  You will need
to use certbot manually if you want to get a certificate from letsencrypt.
If you wish to disable HTTPS completely you can do so by adding
a `-e '{"tls_enabled": false}'` switch to your `ansible-playbook` command.


# Instance Identification

Instances need to be properly tagged to be found by ansible.  The tags are:

* role: `buildbot-master` for the master
* role: `buildbot-linux-worker` for the Linux worker
* role: `buildbot-windows-worker` for the Windows worker
