This script verifies the integrity of Golem's Docker hub images.

In order to do that, a registry of docker images required by Golem is defined in
the `image_integrity.ini` file that has a format of:

```
golemfactory/image_name        1.0             sha256-hash-of-the-image
```

The registry holds entries valid for the current branch and must include only
production images.

To run verification, just launch the script:

`./scripts/docker_integrity/verify.py`

To ensure that all docker images used by Golem are included in the verification
check, add a `--verify-coverage` flag:

`./scripts/docker_integrity/verify.py --verify-coverage`

This detects situations when Golem's images have been updated without including
them in the verification and, at the same time, should prevent accidental updates
that cause non-production images to make it into the major branch.

The script will run through all images listed in the registry and will produce
a consistent report.

If all images are found intact, it will exit normally, with an exit code of `0`.

Should it encounter hash mismatches, it will produce a failure report and an
exit code of `1`. It will also exit erroneously if any errors are encountered
that would prevent correct verification of images.
