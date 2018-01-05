
set PROJECT_DIR="%systemdrive%%homepath%\projects"


echo "Activate golem-env"
call "%PROJECT_DIR%\golem-env\Scripts\activate.bat"

echo "Change to source directory"
cd "%PROJECT_DIR%\golem"

echo "Intstall requirements"
pip install -r requirements.txt
pip install -r requirements-win.txt

echo "Run setup.py develop ( no docker )"
set APPVEYOR=TRUE &&python setup.py develop
