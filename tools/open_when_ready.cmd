@echo off
REM Opens the browser once the Flask app actually answers.
REM
REM Uses curl, not PowerShell's Invoke-WebRequest: Windows PowerShell 5.1 sends
REM Invoke-WebRequest through the system proxy, which fails against localhost on
REM this machine even while the server is serving normally. curl and a raw
REM socket both succeed, so curl is the reliable probe here.
setlocal
set URL=http://localhost:5003/
for /l %%i in (1,1,120) do (
    curl -s -o nul %URL%
    if not errorlevel 1 goto :open
    timeout /t 1 /nobreak >nul
)
echo Servern svarade inte inom 120 sekunder.
exit /b 1

:open
start "" %URL%
exit /b 0
