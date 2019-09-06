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

* **UC3:** **`force_accept`** - Force Accept scenario where, having
acknowledged reception of the task results, the Requestor doesn't respond
with either `SubtaskResultsAccepted` or `SubtaskResultsRejected` message.
In this case, the Provider seeks the Concent's mediation to acquire
the accept/reject decision from the Requestor or - in case when even
the Concent fails to contact the Requestor - to receive payment for
the completed subtask.

* **UC4:** **`additional_verification`** - Additional Verification scenario,
triggered after the Requestor rejects the results from the Provider.
Because Provider is sure they executed their task according to the specs,
they are forced to contact the Concent service to ask for an independent
verification of the same task to confirm their correctness despite Requestor's
decision to the contrary. In order to do that, the Provider must supply their
own deposit which will be charged by the Concent if the verification confirms
Requestor's rejection. Otherwise, if the Concent finds the results correct,
they'll both pay the Provider from Requestor's deposit and charge the Requestor
for the additonal verification performed.

* **UC5:** **`force_payment`** - Force Payment scenario, executed in case,
after a specified timeout, the Requestor fails to execute the payment for any
tasks executed by the Provider, which the Requestor earlier confirmed as
successful by sending `SubtaskResultsAccepted`. Provider then files a complaint
with the Concent, containing the list of unpaid commitments and, after Concent
confirms in the blockchain that the payments have indeed not been paid, pays
for them from the Requestor's deposit.


### Concent variant

The tests use the `staging` variant of the Concent by default.
One can choose a different variant by supplying the
`CONCENT_VARIANT` environment variable, e.g.:

```
$ CONCENT_VARIANT=test pytest scripts/concent_acceptance_tests
``` 

