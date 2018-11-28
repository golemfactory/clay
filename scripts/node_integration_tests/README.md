# Golem node integration tests

This module contains the local node integration tests.
These tests run provider-requestor pairs of full `golem` nodes locally
to test various interactions of golem instances.

As pairs of nodes are created each time a single test is run,
please keep in mind that those tests usually take a long time to execute,
on the order of several minutes per single test.

The tests consist of two major parts:
* `golem` - the tests that strictly test interactions between
two golem instances
* `concent`- the tests that run instance pairs in such way as to trigger
Concent Service calls and test whether the task runs still complete
correctly when Concent is involved.

## How the tests work

Each test in this suite spawns of a pair of nodes - a provider and
a requestor. Those can be either perfectly normal, unmodified Golem nodes,
or tweaked nodes - usually on just one end - that display some unstandard
behavior - e.g. a requestor node that always fails the submitted results.

This allows us to simulate various scenarios of two nodes interacting with
each other and verifying they do indeed react the way we intend them to.

We could theoretically create tests that employ more than two golem instances
but we don't do that yet and it's not yet supported by the test suite. 

### Components

Here's the list of components that make up the test suite.

#### nodes

The scripts that run the actual golem processes and which can
introduce modifications to the regular node behavior, implemented using
`mock`

#### playbooks

The scripts for the tests themselves, each of which is an instance of
`playbooks.base.NodeTestPlaybook` and is comprised of discrete steps
through which the execution of the test progresses.

After both golem instances are spawned, most of the steps consist of RPC calls
to either the requestor or to the provider node and checking for expected
output in subsequent phases of the test, which usually means during subsequent
phases of a task execution.

In the very few cases where RPC calls are unavailable for a given check,
Golem's standard output can be sieved through for expected entries.


#### rpc

The RPC client used by the playbooks to connect to the golem nodes' RPC
endpoints.

#### tasks

The task definitions and the task resources used by the tests.

Local task packages can be added to `tasks/_local` in order to run the
integration tests with other payloads. In order to do so, specify the task
resource package using the `--task-package` parameter to `run_test.py`.

It's also possible to execute a single run of a playbook with an overridden
task definition using the `--task-settings` parameter of `run_test.py`. The
parameter points to a definition in `tasks/__init__.py` so the key must exist
there.

#### tests

The unittest definitions that allow the tests to be executed using a unit test
runner (e.g. `pytest`) and which are responsible for wrapping the playbook
runs with the code that creates the provider and requestor data directories so
that they can be later retrieved and uploaded as an artifact in the CI
environment.

#### run_nodes.py

The script that just launches the node pair that can be used after a test
to launch the nodes again and possibly perform some post-mortem or otherwise
further interact with one or both of the tested nodes.

```
usage: run_nodes.py [-h] [--provider-datadir PROVIDER_DATADIR]
                    [--requestor-datadir REQUESTOR_DATADIR]

Run a pair of golem nodes with default test parameters

optional arguments:
  -h, --help            show this help message and exit
  --provider-datadir PROVIDER_DATADIR
                        the provider node's datadir
  --requestor-datadir REQUESTOR_DATADIR
                        the requestor node's datadir

```

#### run_test.py

The script that runs a single test - iow, a single playbook and which allows
the test run to customized further with additional parameters, not available
when running through `pytest`.


## Running the tests

The tests can be run in two ways - either directly, using the script that
launches the two nodes with a specific playbook or by invoking `pytest`
(or another unittest runner) and pointing it to the integration test location.

### Running with run_test.py

You can run a single test directly with the `run_test.py` script, which allows
you to specify additional parameters.

example:

```
./scripts/node_integration_tests/run_test.py golem.regular_run.RegularRun
```

full usage:

```
run_test.py [-h] [--task-package TASK_PACKAGE]
            [--task-settings TASK_SETTINGS]
            [--provider-datadir PROVIDER_DATADIR]
            [--requestor-datadir REQUESTOR_DATADIR] [--mainnet]
            playbook_class

Runs a single test playbook.

positional arguments:
  playbook_class        a dot-separated path to the playbook class within
                        `playbooks`, e.g. golem.regular_run.RegularRun

optional arguments:
  -h, --help            show this help message and exit
  --task-package TASK_PACKAGE
                        a directory within `tasks` containing the task package
  --task-settings TASK_SETTINGS
                        the task settings set to use, see `tasks.__init__.py`
  --provider-datadir PROVIDER_DATADIR
                        the provider node's datadir
  --requestor-datadir REQUESTOR_DATADIR
                        the requestor node's datadir
  --mainnet             use the mainnet environment to run the test (the
                        playbook must also use mainnet)

```

### Running with pytest

Alternatively, you may choose to run the whole suite using `pytest`.

```
pytest scripts/node_integration_tests
```

If you need to control where the test artifacts are stored - e.g. in order to 
upload them as the CI build artifact after the whole run, you can provide the
root directory for all the artifacts in the `GOLEM_INTEGRATION_TEST_DIR`
environment variable, e.g.:
 
```
GOLEM_INTEGRATION_TEST_DIR=/some/location pytest scripts/node_integration_tests
```

And finally, to run a single test using `pytest`, just use standard `pytest`
syntax, e.g.:

```
pytest scripts/node_integration_tests/tests/test_golem.py::GolemNodeTest::test_regular_task_run
```

Suggestion: when you _don't_ provide the `GOLEM_INTEGRATION_TEST_DIR` variable
to pytest, run `pytest -s -v [...]` so that you can see the paths generated
automatically during the test run.
