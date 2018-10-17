
call ".\golem_source__prep.bat"

echo "Running golem with DEBUG logs"
python golemapp.py --loglevel DEBUG

pause
