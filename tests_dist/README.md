# Testing golem dist packages

This folder is dedicated to testing the packages pyinstaller creates for golem in the dist/ folder

- [x] Add first test, `tests/test_version.py`
  - [x] Consistent versioning with --abbrev @prekucki
- [x] Add runner for this test, `runner.py`
- [x] Add fixture to assist testing this way `lib.py.ProcTester`
- [x] Multiple tests parallel @maaktweluit
- [ ] Test step config ( based on logs ) @maaktweluit
  - [x] new tests case to mock longer runs `tests/test_started.py`
  - [x] Use case: run 1 requestor on the test network without concent
  - [ ] Fix cross platform task json ( copy fix from prekucki test )
- [ ] Infrastructure setup @prekucki
- [ ] Generate report @prekucki
- [ ] Use case: run 3 nodes, wait for boot, run test, victory
- [ ] document / make utils for `tests/config.json`
- [ ] Test agent config
- [ ] Store logs in artifact
- [ ] Test step config ( Replace logs checks with rpc / cli calls )
- [ ] Add logging, replace `print('DEBUG` with logger.debug
- [ ] Add regex like matching in expect `stdout` and `stderr`
   - [x] check for startswith when line starts with ^
   - [ ] allow string or regex matches by the first character `exp_line[:1]`, 's' for string, 'r' for regex?
- [ ] Add missing logs for tests
  - [ ] Requested computation succesfull ( to replace WARNING in `test_requestor.py` )
- [ ] Check windows process tree
  - [ ] `CTRL_C_EVENT` is send to the whole tree, maybe also implement `CTRL_BREAK_EVENT`?
  - [ ] Proc seems to continue after exiting, closes cleanly a few seconds after

