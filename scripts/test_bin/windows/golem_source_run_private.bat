
call ".\golem_source__prep.bat"

set ID=99

echo "Running golem on network '%ID%'"
python golemapp.py --protocol_id %ID%

pause
