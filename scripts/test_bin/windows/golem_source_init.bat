
set PROJECT_DIR=%systemdrive%%homepath%\projects

echo "Ensure projects directory exists"
if not exist "%PROJECT_DIR%" md "%PROJECT_DIR%"

echo "Setup venv in ~/projects/golem-env"
python -m venv "%PROJECT_DIR%\golem-env"

echo "Clone into ~/projects/golem"
git clone https://github.com/golemfactory/golem "%PROJECT_DIR%\golem"

set CUR_DIR=%CD%

echo "Change directory to ~/projects/golem"
cd "%PROJECT_DIR%\golem"

echo "Build taskcollector"
msbuild apps\rendering\resources\taskcollector\taskcollector.sln /p:Configuration=Release /p:Platform=x64

echo "Run update from previous directory"
cd %CUR_DIR%
call ".\golem_source_update.bat"
