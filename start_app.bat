@echo off
REM ============================================================
REM  AI Agent Lab — Quick Start (Batch Wrapper)
REM  用法:
REM    start_app.bat          (dev 模式)
REM    start_app.bat prod     (prod 模式)
REM ============================================================

set ENV=%1
if "%ENV%"=="" set ENV=dev

echo.
echo   AI Agent Lab — Starting in [%ENV%] mode ...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0start_app.ps1" -Env %ENV%
