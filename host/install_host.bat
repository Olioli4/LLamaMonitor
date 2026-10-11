@echo off
setlocal
set "HOST_DIR=%~dp0"
set "JSON_PATH=%HOST_DIR%com.llama.smi_host.json"
set "EXE_PATH=%HOST_DIR%smi_bridge.exe"
set "CS_PATH=%HOST_DIR%smi_host.cs"
set "DEFAULT_ID=mogoecckabfchcngfnfgebnhdfmgafpd"

if not "%~1"=="" (
    if not "%~1"=="non-interactive" (
        set "EXT_ID=%~1"
    ) else (
        set "EXT_ID=%DEFAULT_ID%"
    )
) else (
    set "EXT_ID=%DEFAULT_ID%"
)

echo Registering Native Messaging Host for Google Chrome...
echo Extension ID: %EXT_ID%

REM Compile native smi_bridge.exe if it does not exist
if not exist "%EXE_PATH%" (
    echo Compiling native smi_bridge.exe with Windows csc.exe...
    "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:exe /out:"%EXE_PATH%" "%CS_PATH%"
)

REM Generate dynamic JSON pointing directly to smi_bridge.exe
powershell -NoProfile -Command ^
  "$json = @{ name = 'com.llama.smi_host'; description = 'Universal llama.cpp Monitor SMI Bridge'; path = (Resolve-Path '%EXE_PATH%').Path; type = 'stdio'; allowed_origins = @('chrome-extension://' + '%EXT_ID%' + '/') };" ^
  "$json | ConvertTo-Json | Set-Content -Path '%JSON_PATH%' -Encoding UTF8"

REM Register in HKCU for Google Chrome
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.llama.smi_host" /ve /t REG_SZ /d "%JSON_PATH%" /f >nul
if %errorlevel% equ 0 (
    echo [SUCCESS] Host successfully registered in Chrome registry!
    echo Key: HKCU\Software\Google\Chrome\NativeMessagingHosts\com.llama.smi_host
    echo Executable: %EXE_PATH%
    echo Manifest: %JSON_PATH%
) else (
    echo [ERROR] Failed to write registry key.
    exit /b 1
)

REM Also register in Edge
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.llama.smi_host" /ve /t REG_SZ /d "%JSON_PATH%" /f >nul

echo Done.
if "%~1"=="" pause
