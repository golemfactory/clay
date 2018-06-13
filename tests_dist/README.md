# Testing golem dist packages

This folder is dedicated to testing the packages pyinstaller creates for golem in the dist/ folder

- [x] Add first test, `tests/test_version.py`
  - [ ] Consistent versioning with --abbrev @prekucki
- [x] Add runner for this test, `runner.py`
- [x] Add fixture to assist testing this way `lib.py.ProcTester`
- [x] Multiple tests parallel @maaktweluit
- [ ] Test step config ( based on logs ) @maaktweluit
  - [x] new tests case to mock longer runs `tests/test_started.py`
  - [ ] Use case: run 3 nodes, wait for boot, run test, victory
  - [ ] document / make utils for `tests/config.json`
- [ ] Infrastructure setup @prekucki
- [ ] Generate report @prekucki
- [ ] Test agent config
- [ ] Store logs in artifact
- [ ] Test step config ( Replace logs checks with rpc / cli calls )
