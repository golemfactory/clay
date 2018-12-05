
set PROJECT_DIR=%systemdrive%%homepath%\projects

echo "Activate golem-env"
call "%PROJECT_DIR%\golem-env\Scripts\activate.bat"

echo "Change to source directory"
cd "%PROJECT_DIR%\golem"
