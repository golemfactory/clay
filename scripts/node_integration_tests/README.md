## Golem node integration tests

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

### Running the tests

The tests can be run in two ways:

* directly, by running specific tests from the shell, e.g.:
`./scripts/node_integration_tests/run_test.py golem.regular_run.RegularRun`
* or by pointning `pytest` to the integration test directory

