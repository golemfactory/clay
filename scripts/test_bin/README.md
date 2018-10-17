# Golem test scripts

This is a list of "clickable" helper scripts to control  running golem.

## From source
Scripts prefixed with `golem_source_` will control running and updating golem from source.

_Init is still a work in progress, please install dependencies first from the wiki guides "Running from source"_
- *init*
  - TODO: Install Dependencies
  - Create ~/projects folder
  - Clone golem
  - Initialize golem-env
  - Create docker-machine ( mac )
  - call "update"
- *update*
  - load venv
  - Install requirements
  - Setup.py develop
- *run*
  - load venv
  - load docker-env ( mac )
- *run_debug*
  as "run", adding argument to log DEBUG
- *run_private*
  as "run", adding argument run on network 99
  TODO: store in user home folder?

