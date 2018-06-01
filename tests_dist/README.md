# Testing golem dist packages

This folder is dedicated to testing the packages pyinstaller creates for golem in the dist/ folder

- [x] Add first test, `tests/test_version.py`
  - [ ] Consistent versioning with --abbrev @prekucki
- [x] Add runner for this test, `runner.py`
- [x] Add fixture to assist testing this way `ProcTestFixture.py`
- [ ] Multiple tests parallel @maaktweluit
- [ ] Test step config ( based on logs ) @maaktweluit
  - [ ] `tests/config.json`
  - [ ] Use case: run 3 nodes, wait for boot, run test, victory
- [ ] Test agent config
- [ ] Infrastructure setup @prekucki
- [ ] Store logs in artifact
- [ ] Generate report @prekucki
- [ ] Test step config ( Replace logs checks with rpc / cli calls )
