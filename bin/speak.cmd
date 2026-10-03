@echo off
setlocal EnableExtensions
for %%I in ("%~dp0..") do set "PLUGIN_ROOT=%%~fI"
if not defined SPEAK_HOME set "SPEAK_HOME=%USERPROFILE%\.cache\speak"
set "SPEAK_PLUGIN_ROOT=%PLUGIN_ROOT%"
set "PYTHON=%SPEAK_HOME%\venv\Scripts\python.exe"
set "STAMP=%SPEAK_HOME%\venv\.speak-stamp"
for %%F in ("%PLUGIN_ROOT%\uv.lock") do set "EXPECTED=%PLUGIN_ROOT%|%%~zF"
set "CURRENT="
if exist "%STAMP%" set /p CURRENT=<"%STAMP%"

if /i "%~1"=="install" goto install
if exist "%PYTHON%" if "%CURRENT%"=="%EXPECTED%" goto run

if /i "%~1"=="hook" (
  start "" /b powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0install.ps1" -Background
  exit /b 0
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" || exit /b 1
goto run

:install
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" || exit /b 1
"%PYTHON%" -m speak setup
exit /b %ERRORLEVEL%

:run
"%PYTHON%" -m speak %*
exit /b %ERRORLEVEL%
