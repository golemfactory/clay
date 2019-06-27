This scripts verifies the integrity of Golem's Docker hub images.

In order to do that, a registry of docker images required by Golem is defined in
`apps/image_integrity.ini` that has a format of:

```
golemfactory/image_name        1.0             sha256-hash-of-the-image
```

The registry holds entries that are valid for the last stable releases plus
those used currently in develop. All entries must be consistent (the script 
verifies if there are no duplicates with differing sha256 hashes and will
raise a `ConfigurationError` if it encounters a conflict).

To run verification, just launch the script:

`./scripts/docker_integrity/verify.py`

The script will run through all images listed in the registry and will produce
a consistent report.

If all images are found intact, it will exit normally, with an exit code of `0`.

Should it encounter hash mismatches, it will produce a failure report and an
exit code of `1`.
