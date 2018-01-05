
set PROJECT_DIR="%systemdrive%%homepath%\projects"

echo "Ensure projects directory exists"
mkdir -p "%PROJECT_DIR%"


echo "Setup venv in ~/projects/golem-env"
python -m venv "%PROJECT_DIR%\golem-env"

echo "Clone into ~/projects/golem"
git clone https://github.com/golemfactory/golem "%PROJECT_DIR%\golem"

call ".\golem_source_update.bat"

