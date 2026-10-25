@echo off
title PixelPie Media Certificate Registration
echo ========================================================
echo   Trusting PixelPie Media Authenticode Certificate
echo ========================================================
certutil -user -addstore -f "TrustedPublisher" "%~dp0PixelPieMedia_RootCA.cer"
echo.
echo [OK] PixelPie Media registered as a Trusted Publisher on this machine.
echo Windows SmartScreen will recognize SDM.exe.
pause
