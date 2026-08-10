@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0graph.ps1" %*
exit /b %ERRORLEVEL%
