@echo off
echo Building Snipix single-file executable...
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller is not installed. Installing it now...
    pip install pyinstaller
)

REM Create the single-file executable
pyinstaller --name=Snipix ^
  --icon=assets/icon.ico ^
  --windowed ^
  --onefile ^
  --clean ^
  --noupx ^
  --add-data "assets;assets" ^
  --exclude-module=pytest ^
  --exclude-module=_pytest ^
  --exclude-module=unittest ^
  --hidden-import=utils ^
  --hidden-import=PIL ^
  --hidden-import=PIL._imagingtk ^
  --hidden-import=PIL._tkinter_finder ^
  main.py

echo.
if %errorlevel% equ 0 (
    echo Build completed successfully!
    echo Executable can be found in the dist folder.
) else (
    echo Build failed with error code %errorlevel%.
)

pause 