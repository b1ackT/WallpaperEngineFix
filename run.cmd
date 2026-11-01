@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Wallpaper Download Fix

echo.
echo   ==========================================================
echo     Wallpaper Download Fix
echo     Repair a corrupted Steam Workshop manifest
echo   ==========================================================
echo.
echo   Steam MUST be fully quit before running this
echo   (right-click the tray icon - Exit).
echo.
echo   Running in DRY-RUN mode first (nothing will be changed)...
echo.

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0wallpaperdownloadfix.ps1" -DryRun

echo.
echo   ----------------------------------------------------------
echo   Dry run finished. Apply the repair now? [Y/N]
echo   ----------------------------------------------------------
set /p ANSWER=  ^> 
if /i not "%ANSWER%"=="Y" (
    echo.
    echo   Cancelled. Nothing was changed.
    goto :end
)

echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0wallpaperdownloadfix.ps1"

:end
echo.
echo   Press any key to close...
pause >nul
