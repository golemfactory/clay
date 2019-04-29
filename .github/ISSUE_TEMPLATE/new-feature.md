---
name: New feature
about: 'Define a new feature / change for Golem '
title: ''
labels: ''
assignees: ''

---

## Rationale
A clear and concise description of what purpose the feature is serving or what problem it's supposed to address.

Any additional context this feature fits into...

## Description

### Functional specification
* What are the components of the required feature?
* What is the designed behavior of those components?
* What are the failure modes and how are they supposed to be handled?

### User Interface
_Are user-facing changes required for this functionality?_
* Description of user-facing behavior
* Changes to existing user interaction?
* Screenshots?

### Technical specification
_If required/possible, provide the detailed description of the required changes in the application_
* Required changes to app's internal structures? Model updates? Model additions?
* Which application modules will be updated?
* Modification of e.g. message handlers?
* Replacement of modules?
* Refactoring?

## Dependencies
_Enumerate other issues the completion of which is critical for this feature to be finished - or which block this feature from progressing with implementation_

### Sub-components
_Define and add links to sub-components_
* ?
* ?

### Blockers
_For any issues that block this issue, add links_
* ?
* ?

### Additional tests
_Enumerate any additional unit and/or integration tests that need to be added for this feature to be covered_
* additional unit tests?
* additional integration tests?


## QA
_Description of the QA process for the feature_

### Test scenarios:

#### Base test process
_specify one of: ( if unsure, consult @ZmijaWA or @ederenn )_
** QA limited to the single feature (in case of very trivial changes)
** Smoke Test (the limited set of tests designed to ensure that most critical functionality doesn't experience regressions)
** Full Test (full set of tests for the whole application - in case of more extensive application updates, refactoring etc)

### New feature tests
_Add test scenarios for the new feature_

#### Positive Scenario 1
* Step 1
* Step 2
* ...
* Expected results

#### Positive Scenario 2
* ...

#### Negative Scenario 1
* Step 1
* Step 2
* ...
* Some expected problem
* Expected problem handling

### Possible regressions
* is there any functionality that is likely to experience regressions?
* are there any existing application components that should be tested more thoroughly?

## Progress

### Development
* [ ] Feature implemented
* [ ] Feature unit/integration tests implemented

### Dev QA
* [ ] Basic tests by the developer pass
* [ ] Unit tests pass
* [ ] Golem integration tests pass
* [ ] Concent integration tests pass
* [ ] Concent acceptance tests pass

### QA team
* [ ] Base scenario passes
* [ ] Additional test 1 passes... 
* [ ] ... 

## Issues encountered during QA
_When adding an issue here, please update testing scenarios and QA progress above_
* [ ] link to issue... 
* [ ] ...
