## Concent acceptance tests

This module contains Concent acceptance tests for each use case.

* **UC1:** **`force_report`**  - Force Report Computed Task scenario
where the Requestor fails to acknowledge reception of the `ReportComputedTask`
message and thus, the Provider uses the Concent service to pass the RCT
message to the Requestor and receive the `AckReportComputedTask` that way.

* **UC2:** **`force_download`** - Forced Download scenario where the
Requestor fails to download the results from the Provider directly and
requests the Concent's assistance in reaching out to the Provider so that the
Provider can upload the results to the Concent's storage whereupon
the Requestor will be able to download them from the Concent.

* **UC3:** **`force_report`** - Force Accept scenario where, having
acknowledged reception of the task results, the Requestor doesn't respond
with either `SubtaskResultsAccepted` or `SubtaskResultsRejected` message.
In this case, the Provider seeks the Concent's mediation to acquire
the accept/reject decision from the Requestor or - in case when even
the Concent fails to contact the Requestor - to receive payment for
the completed subtask.

### Concent variant

The tests use the `staging` variant of the Concent by default.
One can choose a different variant by supplying the
`CONCENT_VARIANT` environment variable, e.g.:

```
$ CONCENT_VARIANT=test pytest scripts/concent_acceptance_tests
``` 

