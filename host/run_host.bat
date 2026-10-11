@echo off
setlocal
set "DIR=%~dp0"
where python >nul 2>nul
if %errorlevel% equ 0 (
    python -u "%DIR%smi_host.py"
) else (
    echo Python not found in PATH 1>&2
    exit /b 1
)
