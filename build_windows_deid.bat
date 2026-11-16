@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade pyinstaller
if errorlevel 1 goto :failure
py -m PyInstaller --noconfirm --clean --onefile --windowed --name METIS_CT_Explorer_DeID metis_csv_explorer_deid.py
if errorlevel 1 goto :failure
echo Build succeeded: dist\METIS_CT_Explorer_DeID.exe
pause
exit /b 0
:failure
echo Build failed. Verify Python and pip are installed.
pause
exit /b 1
