
call ".\golem_source__prep.bat"

echo "Install requirements"
pip install -r requirements.txt
pip install -r requirements-win.txt

echo "Run setup.py develop ( no docker )"
set APPVEYOR=TRUE &&python setup.py develop

pause
